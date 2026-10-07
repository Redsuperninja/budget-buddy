/**
 * Shared plumbing for talking to the Home Base (sync contract v1, section 4): the secure random
 * source, one HTTP request with a hard timeout, and the sealed-box envelope helpers. Used by both
 * pairing (`pairClient.ts`) and syncing (`syncClient.ts`). Keys passed in are never stored or logged.
 */
import * as Crypto from 'expo-crypto';
import nacl from 'tweetnacl';
import { encodeUTF8 } from 'tweetnacl-util';

import { b64uDecode, b64uEncode } from './base64url';
import { PairError } from './pairErrors';
import { isPrivateHost } from './pairingQr';

export const REQUEST_TIMEOUT_MS = 10_000;
/** Pairing and ack answers are tiny. */
export const MAX_BODY_BYTES = 16 * 1024;

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

export function randomBytes(n: number): Uint8Array {
  try {
    installSecureRandom();
    return nacl.randomBytes(n);
  } catch {
    throw new PairError('something_wrong');
  }
}

/**
 * Every request goes through here, so every request is checked: plain http to a private, loopback or
 * link-local IP literal with a real port. A damaged or tampered saved address can never send data elsewhere.
 */
export function assertLocalUrl(url: string): void {
  const m = /^http:\/\/(\[[0-9a-fA-F:.]+\]|[0-9.]+):(\d{1,5})\//.exec(url);
  const host = m ? (m[1].startsWith('[') ? m[1].slice(1, -1) : m[1]) : '';
  const port = m ? Number(m[2]) : 0;
  if (!m || !isPrivateHost(host) || port < 1 || port > 65535) throw new PairError('bad_host');
}

const utf8Length = (text: string): number => new TextEncoder().encode(text).length;

/**
 * Read the body while counting real bytes, and stop (abort) as soon as it is over the limit.
 * Uses the streaming reader when this fetch has one. React Native's built-in fetch may not, in which case
 * we fall back to reading the whole text and then measuring its UTF-8 size (see mobile/README.md).
 */
async function readCapped(res: Response, controller: AbortController, maxBytes: number): Promise<string> {
  const declared = Number(res.headers?.get?.('content-length'));
  if (Number.isFinite(declared) && declared > maxBytes) {
    controller.abort();
    throw new PairError('something_wrong');
  }
  const reader = (res.body as ReadableStream<Uint8Array> | null | undefined)?.getReader?.();
  if (!reader) {
    const text = await res.text();
    if (utf8Length(text) > maxBytes) throw new PairError('something_wrong');
    return text;
  }
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > maxBytes) {
      controller.abort();
      void reader.cancel().catch(() => undefined);
      throw new PairError('something_wrong');
    }
    chunks.push(value);
  }
  const all = new Uint8Array(total);
  let at = 0;
  for (const c of chunks) {
    all.set(c, at);
    at += c.length;
  }
  // Not TextDecoder: older Hermes builds may not have it. tweetnacl-util's `encodeUTF8` turns UTF-8 bytes into a string.
  return encodeUTF8(all);
}

export type HttpResult = { status: number; text: string };

/**
 * One HTTP request. The timer covers the whole answer, including reading the body.
 * Network failures and timeouts become `server_unreachable`; an oversized body becomes `something_wrong`.
 */
export async function httpRequest(
  f: typeof fetch,
  url: string,
  init: { method: 'GET' | 'POST'; headers?: Record<string, string>; body?: string },
  maxBytes: number = MAX_BODY_BYTES,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<HttpResult> {
  assertLocalUrl(url);
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new PairError('server_unreachable'));
    }, timeoutMs);
  });
  const work = (async () => {
    let res: Response;
    let text: string;
    try {
      // A redirect could send the token or sync traffic somewhere else, so never follow one.
      res = await f(url, { ...init, redirect: 'manual', signal: controller.signal });
    } catch {
      throw new PairError('server_unreachable');
    }
    if (res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)) {
      throw new PairError('bad_response');
    }
    try {
      text = await readCapped(res, controller, maxBytes);
    } catch (e) {
      throw e instanceof PairError ? e : new PairError('server_unreachable');
    }
    return { status: res.status, text };
  })();
  work.catch(() => undefined); // avoid an unhandled rejection if the timeout wins
  try {
    return await Promise.race([work, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

/** Parse a JSON object, or null if it is anything else. */
export function parseObject(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text);
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/** Contract 4.2: seal an inner request under `key`. Returns the HTTP body and the request nonce (base64url). */
export function sealRequest(
  key: Uint8Array,
  inner: object,
  ts: number,
  extra: Record<string, string> = {},
  nonce?: Uint8Array,
): { body: string; nonce: string } {
  const n = nonce ?? randomBytes(24); // always a fresh CSPRNG nonce unless a test injects one
  const box = nacl.secretbox(new TextEncoder().encode(JSON.stringify(inner)), n, key);
  const body = JSON.stringify({ v: 1, nonce: b64uEncode(n), ts, ...extra, box: b64uEncode(box) });
  return { body, nonce: b64uEncode(n) };
}

/**
 * Contract 4.3: open an encrypted response and check `type == "res"` and `re` equals our nonce.
 * Anything wrong becomes `bad_response` and the answer is discarded.
 */
export function openResponse(
  outer: Record<string, unknown>,
  key: Uint8Array,
  requestNonce: string,
): Record<string, unknown> {
  try {
    const respNonce = b64uDecode(String(outer.nonce), 24);
    const opened = nacl.secretbox.open(b64uDecode(String(outer.box)), respNonce, key);
    if (!opened) throw new Error('open failed');
    const reply: unknown = JSON.parse(encodeUTF8(opened));
    if (typeof reply !== 'object' || reply === null) throw new Error('not an object');
    const r = reply as Record<string, unknown>;
    if (r.type !== 'res' || r.re !== requestNonce) throw new Error('mismatch');
    return r;
  } catch {
    throw new PairError('bad_response');
  }
}
