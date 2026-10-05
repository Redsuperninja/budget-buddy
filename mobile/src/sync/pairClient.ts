/**
 * Pairing HTTP client: POST /api/pair exactly as in sync contract v1 (sections 2.4, 3.6, 4).
 * The phone makes a fresh keypair, derives `shared`, sends one encrypted request, opens the
 * encrypted answer, and only then returns the credentials. phone_sk and shared never leave this function.
 */
import * as Crypto from 'expo-crypto';
import nacl from 'tweetnacl';
import { encodeUTF8 } from 'tweetnacl-util';

import { b64uDecode, b64uEncode } from './base64url';
import type { Credentials } from './credentials';
import { fromServerCode, PairError } from './pairErrors';
import { baseUrl, CONTRACT_VERSION, type PairingPayload } from './pairingQr';

export const PAIR_PATH = '/api/pair';
export const REQUEST_TIMEOUT_MS = 10_000;

export type PairDeps = {
  fetch?: typeof fetch;
  /** Unix seconds. */
  now?: () => number;
  /** Test hooks. Real pairing leaves these out and uses a fresh random keypair and nonce. */
  phoneSecretKey?: Uint8Array;
  nonce?: Uint8Array;
};

export type DeviceInfo = { deviceName: string; platform: 'ios' | 'android'; appVersion: string };

let prngInstalled = false;

/** Use the phone's secure random source for nacl; fail closed (never Math.random). */
export function installSecureRandom(): void {
  if (prngInstalled) return;
  nacl.setPRNG((x, n) => {
    const bytes = Crypto.getRandomBytes(n);
    if (!bytes || bytes.length !== n) throw new PairError('something_wrong');
    for (let i = 0; i < n; i++) x[i] = bytes[i];
  });
  prngInstalled = true;
}

function randomBytes(n: number): Uint8Array {
  try {
    installSecureRandom();
    return nacl.randomBytes(n);
  } catch {
    throw new PairError('something_wrong');
  }
}

export const MAX_BODY_BYTES = 16 * 1024;

/** One request. The 10 s timer covers the whole answer, including reading the body. */
async function post(f: typeof fetch, url: string, body: string): Promise<{ status: number; text: string }> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new PairError('server_unreachable'));
    }, REQUEST_TIMEOUT_MS);
  });
  const work = (async () => {
    let res: Response;
    let text: string;
    try {
      res = await f(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: controller.signal,
      });
      text = await res.text();
    } catch {
      throw new PairError('server_unreachable');
    }
    if (text.length > MAX_BODY_BYTES) throw new PairError('something_wrong');
    return { status: res.status, text };
  })();
  work.catch(() => undefined); // avoid an unhandled rejection if the timeout wins
  try {
    return await Promise.race([work, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

export async function pairWithComputer(
  qr: PairingPayload,
  device: DeviceInfo,
  deps: PairDeps = {},
): Promise<Credentials> {
  const f = deps.fetch ?? fetch;
  const ts = (deps.now ?? (() => Math.floor(Date.now() / 1000)))();

  let shared: Uint8Array;
  let phonePub: Uint8Array;
  let nonce: Uint8Array;
  try {
    installSecureRandom();
    const keys = deps.phoneSecretKey
      ? nacl.box.keyPair.fromSecretKey(deps.phoneSecretKey)
      : nacl.box.keyPair();
    phonePub = keys.publicKey;
    shared = nacl.box.before(b64uDecode(qr.pair_pub, 32), keys.secretKey);
    nonce = deps.nonce ?? randomBytes(24);
  } catch (e) {
    throw e instanceof PairError ? e : new PairError('something_wrong');
  }

  const inner = {
    type: 'req',
    ts,
    method: 'POST',
    path: PAIR_PATH,
    contract: CONTRACT_VERSION,
    data: {
      code: qr.code,
      device_name: device.deviceName,
      platform: device.platform,
      app_version: device.appVersion,
    },
  };
  const box = nacl.secretbox(new TextEncoder().encode(JSON.stringify(inner)), nonce, shared);
  const body = JSON.stringify({
    v: 1,
    nonce: b64uEncode(nonce),
    ts,
    phone_pub: b64uEncode(phonePub),
    box: b64uEncode(box),
  });

  const res = await post(f, baseUrl(qr.host, qr.port) + PAIR_PATH, body);

  let outer: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(res.text);
    if (typeof parsed === 'object' && parsed !== null) outer = parsed as Record<string, unknown>;
  } catch {
    outer = null;
  }

  // Plaintext errors (the server couldn't open our box). Unauthenticated: just report them.
  const plain = outer?.error as { code?: unknown } | undefined;
  if (plain && typeof plain === 'object') throw fromServerCode(plain.code);
  if (!outer || typeof outer.box !== 'string') {
    if (res.status === 403) throw new PairError('not_home_network');
    throw new PairError(res.status >= 500 ? 'something_wrong' : 'bad_response');
  }

  // Encrypted answer: open with `shared`, check type and re.
  let reply: Record<string, unknown>;
  try {
    const respNonce = b64uDecode(String(outer.nonce), 24);
    const opened = nacl.secretbox.open(b64uDecode(outer.box), respNonce, shared);
    if (!opened) throw new Error('open failed');
    reply = JSON.parse(encodeUTF8(opened));
    if (reply.type !== 'res' || reply.re !== b64uEncode(nonce)) throw new Error('mismatch');
  } catch {
    throw new PairError('bad_response');
  }
  if (reply.status !== 200) {
    throw fromServerCode((reply.error as { code?: unknown } | undefined)?.code);
  }

  const data = reply.data as Record<string, unknown> | undefined;
  try {
    if (!data || typeof data.device_id !== 'number' || !Number.isInteger(data.device_id)) throw new Error();
    if (typeof data.token !== 'string' || typeof data.sync_key !== 'string') throw new Error();
    if (typeof data.server_id !== 'string') throw new Error();
    b64uDecode(data.token, 32);
    b64uDecode(data.sync_key, 32);
    b64uDecode(data.server_id, 16);
  } catch {
    throw new PairError('bad_response');
  }
  if (data.server_id !== qr.server_id) throw new PairError('wrong_server');

  return {
    host: qr.host,
    port: qr.port,
    sync_key: data.sync_key as string,
    token: data.token as string,
    server_id: data.server_id as string,
    server_name: typeof data.server_name === 'string' ? data.server_name.slice(0, 50) : qr.name,
    device_id: data.device_id as number,
  };
}
