import nacl from 'tweetnacl';

import { b64uDecode, b64uEncode } from '../base64url';
import { CREDENTIALS_KEY, getNeedsAttention, loadCredentials, saveCredentials } from '../credentials';
import { PAIR_MESSAGES } from '../pairErrors';
import { SAMPLE_SNAPSHOT } from '../sampleSnapshot';
import { ACK_PATH, HEALTH_PATH, SNAPSHOT_PATH, syncNow } from '../syncClient';
import type { SyncDeps } from '../syncClient';
import { openResponse, sealRequest } from '../transport';

const range = (a: number, b: number) => Uint8Array.from({ length: b - a + 1 }, (_, i) => a + i);

// Contract 4.7, vectors 1 to 3.
const KEY = b64uDecode('AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8', 32);
const V1_PLAINTEXT =
  '{"type":"req","ts":1790000000,"method":"POST","path":"/api/sync/snapshot","contract":1,"data":{}}';
const V1_ENVELOPE =
  '{"v":1,"nonce":"ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3","ts":1790000000,"box":"h3tnJpseU-mZcMCYFrdbMYp7Odw9QnisK0cwHy5klYDKkIe6xiATRIxGA6LyN46Q0n-4rJ-LQ-3zIQDf1_FcItKiwusyFNue2TJQ6OB3Ly7bIX6xJfqbUjm4RRhuulXPJek3maWpfGGPCQ12_-DORKg"}';
const V1_NONCE = 'ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3';
const V2_ENVELOPE = {
  v: 1,
  nonce: 'QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZX',
  ts: 1790000001,
  box: 'hlFMv8abBA-l4oJaaRR4wDE1IQBKNJkQ5CsUEkqleIW9FXxlWnpv-NTlEvrI9aEmsRZTM6f0g20QNU0Ve5s5QMvnTB_rzYAzxKj6ykod04XRmOGWeePezi-F5XD-bD8BYnJcPJt9bVe9XcBjvFOnpeuQUTyfJAe-DC--kT6NYdUvBUQi5_anPPrja69GQjnA3ZUMVuf2DQ',
};

describe('envelope (contract 4.7 vectors)', () => {
  it('vector 1: seals the request exactly like the server expects', () => {
    const inner = JSON.parse(V1_PLAINTEXT);
    expect(JSON.stringify(inner)).toBe(V1_PLAINTEXT);
    const sealed = sealRequest(KEY, inner, 1790000000, {}, range(0x20, 0x37));
    expect(sealed.body).toBe(V1_ENVELOPE);
    expect(sealed.nonce).toBe(V1_NONCE);
  });

  it('vector 2: opens a response with non-ASCII text when re matches', () => {
    const reply = openResponse(V2_ENVELOPE, KEY, V1_NONCE);
    expect(reply.status).toBe(200);
    expect(reply.data).toEqual({ merchant: 'Café Olé', total_cents: 1234 });
  });

  it('vector 2: a wrong re is bad_response', () => {
    expect(() => openResponse(V2_ENVELOPE, KEY, b64uEncode(range(0, 23)))).toThrow(
      expect.objectContaining({ code: 'bad_response' }),
    );
  });

  it('vector 3: a flipped bit in the box fails to open', () => {
    const box = b64uDecode(JSON.parse(V1_ENVELOPE).box);
    box[box.length - 1] ^= 1;
    const outer = { ...JSON.parse(V1_ENVELOPE), box: b64uEncode(box) };
    expect(() => openResponse(outer, KEY, V1_NONCE)).toThrow(expect.objectContaining({ code: 'bad_response' }));
  });

  it('uses a fresh nonce each time', () => {
    const a = sealRequest(KEY, { x: 1 }, 1);
    const b = sealRequest(KEY, { x: 1 }, 1);
    expect(a.nonce).not.toBe(b.nonce);
    expect(b64uDecode(a.nonce, 24)).toHaveLength(24);
  });
});

// --- syncNow against a fake Home Base ------------------------------------------------------------

const NOW = 1790000000;
const TOKEN = 'YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8';
const SYNC_KEY = '4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8';
const SERVER_ID = 'Zk3pR7tQ1xYb9mWc2nLs5Q';
const CREDS = {
  host: '192.168.1.20',
  port: 8765,
  sync_key: SYNC_KEY,
  token: TOKEN,
  server_id: SERVER_ID,
  server_name: 'Home Base',
  device_id: 3,
};
const SNAPSHOT = { ...JSON.parse(JSON.stringify(SAMPLE_SNAPSHOT)), server_id: SERVER_ID };
const key = b64uDecode(SYNC_KEY, 32);

type Reply = { status?: number; inner?: object; plain?: unknown; httpStatus?: number; reNonce?: string };
type Handlers = { health?: () => Promise<unknown> | unknown; snapshot?: (n: number) => Reply; ack?: () => Reply };

/** A fake computer. Opens each request with the sync key and answers with a box bound to its nonce. */
function fakeServer(h: Handlers = {}) {
  const calls: { url: string; init: RequestInit & { headers?: Record<string, string> }; inner?: any; nonce?: string }[] = [];
  let snapshotCalls = 0;
  const f = jest.fn(async (url: string, init: any) => {
    const call: (typeof calls)[number] = { url, init };
    calls.push(call);
    const json = (body: unknown, status = 200) => ({ status, text: async () => JSON.stringify(body) });
    if (url.endsWith(HEALTH_PATH)) {
      return h.health ? h.health() : json({ status: 'ok', version: '0.1.0', contract: 1 });
    }
    const outer = JSON.parse(init.body);
    const opened = nacl.secretbox.open(b64uDecode(outer.box), b64uDecode(outer.nonce, 24), key);
    call.inner = JSON.parse(new TextDecoder().decode(opened!));
    call.nonce = outer.nonce;
    const isSnapshot = url.endsWith(SNAPSHOT_PATH);
    const reply: Reply = isSnapshot
      ? (h.snapshot ?? (() => ({ inner: SNAPSHOT })))(snapshotCalls++)
      : (h.ack ?? (() => ({ inner: { last_sync_at: '2026-10-02T18:30:01Z' } })))();
    if (reply.plain !== undefined) return json(reply.plain, reply.httpStatus ?? 400);
    const status = reply.status ?? 200;
    const innerRes: Record<string, unknown> = { type: 'res', ts: NOW + 1, re: reply.reNonce ?? outer.nonce, status };
    if (status === 200) innerRes.data = reply.inner;
    else innerRes.error = reply.inner;
    const n = nacl.randomBytes(24);
    const box = nacl.secretbox(new TextEncoder().encode(JSON.stringify(innerRes)), n, key);
    return json({ v: 1, nonce: b64uEncode(n), ts: NOW + 1, box: b64uEncode(box) }, status);
  });
  return { f, calls };
}

const run = (server: ReturnType<typeof fakeServer>, extra: Partial<SyncDeps> = {}) => {
  const save = jest.fn(async () => null as string | null);
  const p = syncNow(CREDS, { fetch: server.f as unknown as typeof fetch, now: () => NOW, save, ...extra });
  return { p, save };
};

beforeEach(async () => {
  await saveCredentials(CREDS);
});

describe('syncNow', () => {
  it('checks health, then fetches and saves the snapshot, then acks', async () => {
    const server = fakeServer();
    const { p, save } = run(server);
    const result = await p;
    await result.ackDone;

    expect(server.calls.map((c) => c.url.replace('http://192.168.1.20:8765', ''))).toEqual([
      HEALTH_PATH,
      SNAPSHOT_PATH,
      ACK_PATH,
    ]);
    const snap = server.calls[1];
    expect(snap.init.headers).toEqual({ 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` });
    expect(snap.inner).toEqual({
      type: 'req',
      ts: NOW,
      method: 'POST',
      path: SNAPSHOT_PATH,
      contract: 1,
      data: {},
    });
    expect(JSON.parse(snap.init.body as string).ts).toBe(NOW);
    expect(server.calls[2].inner.data).toEqual({
      snapshot_generated_at: SNAPSHOT.generated_at,
      receipts_uploaded: 0,
      app_version: '1.0.0',
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(result.snapshot.server_id).toBe(SERVER_ID);
    expect(new Set(server.calls.slice(1).map((c) => c.nonce)).size).toBe(2); // fresh nonce per request
  });

  it('does not fetch anything encrypted if the computer cannot be reached', async () => {
    const server = fakeServer({ health: () => Promise.reject(new TypeError('Network request failed')) });
    const { p, save } = run(server);
    await expect(p).rejects.toMatchObject({ code: 'server_unreachable' });
    expect(server.calls).toHaveLength(1);
    expect(save).not.toHaveBeenCalled();
  });

  it('asks for an update when the computer is too old (no contract in health)', async () => {
    const server = fakeServer({ health: () => ({ status: 200, text: async () => JSON.stringify({ status: 'ok' }) }) });
    await expect(run(server).p).rejects.toMatchObject({ code: 'update_needed' });
  });

  it('says not_home_network for a plaintext 403 on health', async () => {
    const server = fakeServer({ health: () => ({ status: 403, text: async () => '{"detail":"nope"}' }) });
    await expect(run(server).p).rejects.toMatchObject({ code: 'not_home_network' });
  });

  it('refuses an answer whose re is not our nonce (bad_response) and saves nothing', async () => {
    const server = fakeServer({ snapshot: () => ({ inner: SNAPSHOT, reNonce: b64uEncode(range(0, 23)) }) });
    const { p, save } = run(server);
    await expect(p).rejects.toMatchObject({ code: 'bad_response' });
    expect(save).not.toHaveBeenCalled();
  });

  it('refuses an answer that is a request, not a response (bad_response)', async () => {
    const f = jest.fn(async (url: string, init: any) => {
      if (url.endsWith(HEALTH_PATH)) return { status: 200, text: async () => '{"contract":1}' };
      const outer = JSON.parse(init.body);
      const n = nacl.randomBytes(24);
      const inner = { type: 'req', ts: NOW, re: outer.nonce, status: 200, data: SNAPSHOT };
      const box = nacl.secretbox(new TextEncoder().encode(JSON.stringify(inner)), n, key);
      return { status: 200, text: async () => JSON.stringify({ v: 1, nonce: b64uEncode(n), ts: NOW, box: b64uEncode(box) }) };
    });
    await expect(syncNow(CREDS, { fetch: f as unknown as typeof fetch, now: () => NOW, save: async () => null })).rejects.toMatchObject({
      code: 'bad_response',
    });
  });

  it('refuses a snapshot from a different computer (wrong_server)', async () => {
    const other = { ...SNAPSHOT, server_id: 'AAECAwQFBgcICQoLDA0ODw' };
    const { p, save } = run(fakeServer({ snapshot: () => ({ inner: other }) }));
    await expect(p).rejects.toMatchObject({ code: 'wrong_server' });
    expect(save).not.toHaveBeenCalled();
  });

  it('refuses a snapshot that fails validation', async () => {
    const { p, save } = run(fakeServer({ snapshot: () => ({ inner: { contract: 1, budget: 'oops' } }) }));
    await expect(p).rejects.toMatchObject({ code: 'bad_response' });
    expect(save).not.toHaveBeenCalled();
  });

  it('asks for an update when the snapshot is from a newer contract', async () => {
    const { p } = run(fakeServer({ snapshot: () => ({ inner: { ...SNAPSHOT, contract: 2 } }) }));
    await expect(p).rejects.toMatchObject({ code: 'update_needed' });
  });

  it('retries once, with a new nonce, after an encrypted replay answer', async () => {
    const server = fakeServer({
      snapshot: (n) => (n === 0 ? { status: 409, inner: { code: 'replay', message: 'x' } } : { inner: SNAPSHOT }),
    });
    const { p } = run(server);
    await p;
    const snaps = server.calls.filter((c) => c.url.endsWith(SNAPSHOT_PATH));
    expect(snaps).toHaveLength(2);
    expect(snaps[0].nonce).not.toBe(snaps[1].nonce);
  });

  it('gives up after a second replay', async () => {
    const server = fakeServer({ snapshot: () => ({ status: 409, inner: { code: 'replay' } }) });
    await expect(run(server).p).rejects.toMatchObject({ code: 'replay' });
    expect(server.calls.filter((c) => c.url.endsWith(SNAPSHOT_PATH))).toHaveLength(2);
  });

  it('does not fail the sync when the ack fails', async () => {
    const server = fakeServer({ ack: () => ({ status: 500, inner: { code: 'server_error' } }) });
    const { p, save } = run(server);
    const result = await p;
    await expect(result.ackDone).resolves.toBeUndefined();
    expect(save).toHaveBeenCalled();
  });

  it('reports a save failure without claiming success', async () => {
    const save = jest.fn(async () => 'disk full');
    const server = fakeServer();
    await expect(
      syncNow(CREDS, { fetch: server.f as unknown as typeof fetch, now: () => NOW, save }),
    ).rejects.toMatchObject({ code: 'something_wrong' });
  });

  it('calls the receipt-upload hook between health and snapshot and reports the count', async () => {
    const order: string[] = [];
    const server = fakeServer();
    const inner = server.f;
    const f = jest.fn(async (url: string, init: any) => {
      order.push(url.replace('http://192.168.1.20:8765', ''));
      return inner(url, init);
    });
    const result = await syncNow(CREDS, {
      fetch: f as unknown as typeof fetch,
      now: () => NOW,
      save: async () => null,
      uploadReceipts: async () => {
        order.push('receipts');
        return 2;
      },
    });
    await result.ackDone;
    expect(order).toEqual([HEALTH_PATH, 'receipts', SNAPSHOT_PATH, ACK_PATH]);
    expect(server.calls[2].inner.data.receipts_uploaded).toBe(2);
  });
});

describe('error mapping and credentials safety (contract 7.2)', () => {
  it.each([
    [400, 'clock_skew'],
    [400, 'bad_request'],
    [403, 'not_home_network'],
    [403, 'bad_host'],
    [413, 'too_large'],
    [426, 'update_needed'],
    [500, 'server_error'],
    [418, 'something_nobody_knows'],
  ])('plaintext %i %s shows our own words and keeps everything', async (httpStatus, code) => {
    const server = fakeServer({ snapshot: () => ({ plain: { error: { code, message: 'SERVER WORDS', server_time: 5 } }, httpStatus }) });
    const raw = JSON.stringify(CREDS);
    const err = await run(server).p.catch((e) => e);
    const expected = PAIR_MESSAGES[(code in PAIR_MESSAGES ? code : 'something_wrong') as keyof typeof PAIR_MESSAGES];
    expect(err.message).toBe(expected);
    expect(err.message).not.toContain('SERVER WORDS');
    expect(await loadCredentials()).toEqual(CREDS);
    expect(JSON.stringify(await loadCredentials())).toBe(raw);
    expect(await getNeedsAttention()).toBe(false);
  });

  it('clock_skew is not retried with the server time', async () => {
    const server = fakeServer({ snapshot: () => ({ plain: { error: { code: 'clock_skew', server_time: NOW + 9999 } }, httpStatus: 400 }) });
    await expect(run(server).p).rejects.toMatchObject({ code: 'clock_skew' });
    expect(server.calls.filter((c) => c.url.endsWith(SNAPSHOT_PATH))).toHaveLength(1);
  });

  it.each(['not_paired', 'device_revoked', 'decrypt_failed'])(
    'plaintext %s raises the Pair again flag but never deletes the credentials',
    async (code) => {
      const server = fakeServer({ snapshot: () => ({ plain: { error: { code } }, httpStatus: 401 }) });
      await expect(run(server).p).rejects.toMatchObject({ code });
      expect(await getNeedsAttention()).toBe(true);
      expect(await loadCredentials()).toEqual(CREDS);
      // A faked error must not have touched the secure-store item either.
      const SecureStore = require('expo-secure-store');
      expect(await SecureStore.getItemAsync(CREDENTIALS_KEY)).toBe(JSON.stringify(CREDS));
    },
  );

  it('the next successful sync clears the flag', async () => {
    const bad = fakeServer({ snapshot: () => ({ plain: { error: { code: 'device_revoked' } }, httpStatus: 401 }) });
    await run(bad).p.catch(() => undefined);
    expect(await getNeedsAttention()).toBe(true);
    await run(fakeServer()).p;
    expect(await getNeedsAttention()).toBe(false);
  });

  it('treats a plaintext 403 with no error body as not_home_network', async () => {
    const f = jest.fn(async (url: string) =>
      url.endsWith(HEALTH_PATH)
        ? { status: 200, text: async () => '{"contract":1}' }
        : { status: 403, text: async () => '{"detail":"no"}' },
    );
    await expect(
      syncNow(CREDS, { fetch: f as unknown as typeof fetch, now: () => NOW, save: async () => null }),
    ).rejects.toMatchObject({ code: 'not_home_network' });
  });

  it('times out with AbortController and says the computer cannot be reached', async () => {
    jest.useFakeTimers();
    try {
      let aborted = false;
      const f = jest.fn((_url: string, init: any) => {
        init.signal.addEventListener('abort', () => (aborted = true));
        return new Promise(() => undefined);
      });
      const p = syncNow(CREDS, { fetch: f as unknown as typeof fetch, now: () => NOW, save: async () => null }).catch((e) => e);
      await jest.advanceTimersByTimeAsync(10_001);
      expect((await p).code).toBe('server_unreachable');
      expect(aborted).toBe(true);
    } finally {
      jest.useRealTimers();
    }
  });

  it('refuses stored credentials that are malformed without deleting them', async () => {
    const bad = { ...CREDS, sync_key: 'AAAA' };
    const f = jest.fn();
    await expect(
      syncNow(bad, { fetch: f as unknown as typeof fetch, now: () => NOW, save: async () => null }),
    ).rejects.toMatchObject({ code: 'not_paired' });
    expect(f).not.toHaveBeenCalled();
    expect(await loadCredentials()).toEqual(CREDS);
  });
});
