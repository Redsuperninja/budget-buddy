/**
 * Sync client (sync contract v1, sections 3.5, 3.8, 3.9, 4, 7.2 and 8).
 *
 * Steps: health check, (receipt upload hook, roadmap #20), snapshot, save, best-effort ack.
 *
 * Security rules this file keeps:
 * - Every request gets a fresh CSPRNG nonce; every answer must be `type == "res"` with `re` equal to
 *   that nonce, or it is thrown away as `bad_response`.
 * - Plaintext errors are unauthenticated (anyone on the Wi-Fi can fake one). They are turned into a
 *   message and, for not_paired / device_revoked / decrypt_failed, a "Pair again" flag. They NEVER
 *   delete the token, the sync key or the saved snapshot.
 * - No retry with the server's clock (contract 4.4). `clock_skew` just shows the clock message.
 * - Nothing secret is logged.
 */
import { APP_VERSION } from '@/lib/appVersion';

import { b64uDecode } from './base64url';
import { getNeedsAttention, setNeedsAttention } from './credentials';
import type { Credentials } from './credentials';
import { fromServerCode, NEEDS_ATTENTION_CODES, PairError } from './pairErrors';
import { baseUrl, CONTRACT_VERSION, isPrivateHost } from './pairingQr';
import { parseSnapshot, SNAPSHOT_UPDATE_MESSAGE } from './snapshot';
import type { Snapshot } from './snapshot';
import { httpRequest, MAX_BODY_BYTES, openResponse, parseObject, sealRequest } from './transport';

export { getNeedsAttention };

export const HEALTH_PATH = '/api/health';
export const SNAPSHOT_PATH = '/api/sync/snapshot';
export const ACK_PATH = '/api/sync/ack';
export const RECEIPTS_PATH = '/api/sync/receipts';
/** The answer to a receipt batch is a short list of results. */
export const MAX_RECEIPT_ANSWER_BYTES = 64 * 1024;
/** A batch can be several MB over home Wi-Fi: more time than a small request. */
export const RECEIPT_TIMEOUT_MS = 120_000;
/** A snapshot is bigger than a pairing answer; still capped so a bad server can't fill the phone's memory. */
export const MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024;

export type SyncDeps = {
  fetch?: typeof fetch;
  /** Unix seconds. */
  now?: () => number;
  appVersion?: string;
  /**
   * Receipt upload (roadmap #20, contract section 8 step 2), called after the health check and before
   * the snapshot with `send`, which posts one batch through the encrypted envelope. Returns how many
   * receipts the Home Base now has (`receipts/receiptUpload.ts`).
   */
  uploadReceipts?: (send: (data: { receipts: object[] }) => Promise<Record<string, unknown>>) => Promise<number>;
  /** Saves the validated snapshot on the phone. Return an error message, or null when saved. */
  save: (snapshot: Snapshot) => Promise<string | null>;
};

export type SyncResult = {
  snapshot: Snapshot;
  /** Resolves when the best-effort ack is finished (never rejects). The UI does not wait for it. */
  ackDone: Promise<void>;
};

function checkCredentials(c: Credentials): Uint8Array {
  // The saved address is checked again every time, in case storage was damaged or tampered with.
  if (
    !isPrivateHost(c.host) ||
    !Number.isInteger(c.port) ||
    c.port < 1 ||
    c.port > 65535 ||
    typeof c.server_id !== 'string'
  ) {
    throw new PairError('not_paired');
  }
  try {
    b64uDecode(c.server_id, 16);
    b64uDecode(c.token, 32);
    return b64uDecode(c.sync_key, 32);
  } catch {
    throw new PairError('not_paired');
  }
}

/** Step 1: GET /api/health. Plaintext and unauthenticated; used to tell "not reachable" from other failures. */
async function checkHealth(f: typeof fetch, c: Credentials): Promise<void> {
  const res = await httpRequest(f, baseUrl(c.host, c.port) + HEALTH_PATH, { method: 'GET' });
  const body = parseObject(res.text);
  if (res.status === 403) {
    const err = body?.error as { code?: unknown } | undefined;
    throw err && typeof err === 'object' ? fromServerCode(err.code) : new PairError('not_home_network');
  }
  if (res.status !== 200 || !body) {
    throw new PairError(res.status >= 500 ? 'something_wrong' : 'bad_response');
  }
  if (body.contract !== CONTRACT_VERSION) throw new PairError('update_needed');
}

/**
 * One encrypted POST. Returns the inner `data`. Throws PairError for everything else.
 * `replay` (a 409 inside the encrypted answer) is retried once with a new nonce, as contract 7.2 says.
 */
export async function encryptedPost(
  f: typeof fetch,
  c: Credentials,
  key: Uint8Array,
  path: string,
  data: object,
  now: () => number,
  maxBytes: number,
  timeoutMs?: number,
): Promise<Record<string, unknown>> {
  for (let attempt = 0; ; attempt++) {
    const ts = now();
    const inner = { type: 'req', ts, method: 'POST', path, contract: CONTRACT_VERSION, data };
    const sealed = sealRequest(key, inner, ts); // fresh random nonce every time, including a retry
    const res = await httpRequest(
      f,
      baseUrl(c.host, c.port) + path,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${c.token}` },
        body: sealed.body,
      },
      maxBytes,
      timeoutMs,
    );

    const outer = parseObject(res.text);
    // Plaintext error: nobody has proven who sent it. Report it, change nothing but the flag.
    const plain = outer?.error as { code?: unknown } | undefined;
    if (plain && typeof plain === 'object') throw fromServerCode(plain.code);
    if (!outer || typeof outer.box !== 'string') {
      if (res.status === 403) throw new PairError('not_home_network');
      throw new PairError(res.status >= 500 ? 'something_wrong' : 'bad_response');
    }

    const reply = openResponse(outer, key, sealed.nonce);
    if (reply.status === 200) {
      const d = reply.data;
      if (typeof d !== 'object' || d === null || Array.isArray(d)) throw new PairError('bad_response');
      return d as Record<string, unknown>;
    }
    const err = fromServerCode((reply.error as { code?: unknown } | undefined)?.code);
    if (err.code === 'replay' && attempt === 0) continue;
    throw err;
  }
}

async function sendAck(
  f: typeof fetch,
  c: Credentials,
  key: Uint8Array,
  snapshot: Snapshot,
  receiptsUploaded: number,
  now: () => number,
  appVersion: string,
): Promise<void> {
  try {
    await encryptedPost(
      f,
      c,
      key,
      ACK_PATH,
      {
        snapshot_generated_at: snapshot.generated_at,
        receipts_uploaded: receiptsUploaded,
        app_version: appVersion,
      },
      now,
      MAX_BODY_BYTES,
    );
  } catch {
    // Best effort (contract section 8 step 4): not shown to the user.
  }
}

/**
 * Run one sync. Resolves after the snapshot is saved (that is the moment a sync counts as successful).
 * Throws a PairError whose `message` is plain English and safe to show.
 */
export async function syncNow(creds: Credentials, deps: SyncDeps): Promise<SyncResult> {
  const f = deps.fetch ?? fetch;
  const now = deps.now ?? (() => Math.floor(Date.now() / 1000));
  const appVersion = deps.appVersion ?? APP_VERSION;

  try {
    const key = checkCredentials(creds);
    await checkHealth(f, creds);

    // Contract section 8 step 2: queued receipts first, so the snapshot can include them. Only an
    // unreachable computer stops the sync; any other receipt problem leaves them queued for next time.
    let receiptsUploaded = 0;
    if (deps.uploadReceipts) {
      try {
        receiptsUploaded = await deps.uploadReceipts((batch) =>
          encryptedPost(f, creds, key, RECEIPTS_PATH, batch, now, MAX_RECEIPT_ANSWER_BYTES, RECEIPT_TIMEOUT_MS),
        );
      } catch (e) {
        // Errors about this phone itself (not paired, revoked, can't decrypt) come back from the snapshot
        // step just below, which reports them and sets "needs attention", so they needn't stop here.
        if (e instanceof PairError && e.code === 'server_unreachable') throw e;
      }
    }

    const data = await encryptedPost(f, creds, key, SNAPSHOT_PATH, {}, now, MAX_SNAPSHOT_BYTES);
    const parsed = parseSnapshot(data);
    if (!parsed.ok) {
      throw new PairError(parsed.message === SNAPSHOT_UPDATE_MESSAGE ? 'update_needed' : 'bad_response');
    }
    if (parsed.snapshot.server_id !== creds.server_id) throw new PairError('wrong_server');

    const saveError = await deps.save(parsed.snapshot);
    if (saveError !== null) throw new PairError('something_wrong');

    await setNeedsAttention(false);
    const ackDone = sendAck(f, creds, key, parsed.snapshot, receiptsUploaded, now, appVersion);
    return { snapshot: parsed.snapshot, ackDone };
  } catch (e) {
    const err = e instanceof PairError ? e : new PairError('something_wrong');
    if (NEEDS_ATTENTION_CODES.includes(err.code)) await setNeedsAttention(true);
    throw err;
  }
}
