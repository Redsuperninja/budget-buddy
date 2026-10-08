/**
 * Pairing HTTP client: POST /api/pair exactly as in sync contract v1 (sections 2.4, 3.6, 4).
 * The phone makes a fresh keypair, derives `shared`, sends one encrypted request, opens the
 * encrypted answer, and only then returns the credentials. phone_sk and shared never leave this function.
 * The envelope, timeout and random-number plumbing is shared with syncing in `transport.ts`.
 */
import nacl from 'tweetnacl';

import { b64uDecode, b64uEncode } from './base64url';
import type { Credentials } from './credentials';
import { fromServerCode, PairError } from './pairErrors';
import { baseUrl, CONTRACT_VERSION, type PairingPayload } from './pairingQr';
import {
  httpRequest,
  installSecureRandom,
  MAX_BODY_BYTES,
  openResponse,
  parseObject,
  randomBytes,
  REQUEST_TIMEOUT_MS,
  sealRequest,
} from './transport';

export { installSecureRandom, MAX_BODY_BYTES, REQUEST_TIMEOUT_MS };

export const PAIR_PATH = '/api/pair';

export type PairDeps = {
  fetch?: typeof fetch;
  /** Unix seconds. */
  now?: () => number;
  /** Test hooks. Real pairing leaves these out and uses a fresh random keypair and nonce. */
  phoneSecretKey?: Uint8Array;
  nonce?: Uint8Array;
};

export type DeviceInfo = { deviceName: string; platform: 'ios' | 'android'; appVersion: string };

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
  const sealed = sealRequest(shared, inner, ts, { phone_pub: b64uEncode(phonePub) }, nonce);

  const res = await httpRequest(
    f,
    baseUrl(qr.host, qr.port) + PAIR_PATH,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: sealed.body },
  );

  const outer = parseObject(res.text);

  // Plaintext errors (the server couldn't open our box). Unauthenticated: just report them.
  const plain = outer?.error as { code?: unknown } | undefined;
  if (plain && typeof plain === 'object') throw fromServerCode(plain.code);
  if (!outer || typeof outer.box !== 'string') {
    if (res.status === 403) throw new PairError('not_home_network');
    throw new PairError(res.status >= 500 ? 'something_wrong' : 'bad_response');
  }

  // Encrypted answer: open with `shared`, check type and re.
  const reply = openResponse(outer, shared, sealed.nonce);
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
