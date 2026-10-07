import { loadCredentials, saveCredentials } from '../credentials';
import { pairWithComputer } from '../pairClient';
import { syncNow } from '../syncClient';
import { httpRequest } from '../transport';

const NOW = 1790000000;
const CREDS = {
  host: '192.168.1.20',
  port: 8765,
  sync_key: '4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8',
  token: 'YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8',
  server_id: 'Zk3pR7tQ1xYb9mWc2nLs5Q',
  server_name: 'Home Base',
  device_id: 3,
};
const go = (creds: typeof CREDS, f: jest.Mock) =>
  syncNow(creds, { fetch: f as unknown as typeof fetch, now: () => NOW, save: async () => null });

beforeEach(async () => {
  await saveCredentials(CREDS);
});

describe('saved address is checked every time', () => {
  it.each([
    ['a public host', { ...CREDS, host: '8.8.8.8' }],
    ['a hostname', { ...CREDS, host: 'evil.example.com' }],
    ['port 0', { ...CREDS, port: 0 }],
    ['port 70000', { ...CREDS, port: 70000 }],
    ['a fractional port', { ...CREDS, port: 80.5 }],
    ['a short server_id', { ...CREDS, server_id: 'AAAA' }],
  ])('refuses saved credentials with %s and sends nothing', async (_n, creds) => {
    const f = jest.fn();
    await expect(go(creds, f)).rejects.toMatchObject({ code: 'not_paired' });
    expect(f).not.toHaveBeenCalled();
    expect(await loadCredentials()).toEqual(CREDS); // nothing deleted
  });

  it('httpRequest itself refuses a non-private address or non-http', async () => {
    const f = jest.fn();
    await expect(httpRequest(f, 'http://8.8.8.8:80/api/health', { method: 'GET' })).rejects.toMatchObject({ code: 'bad_host' });
    await expect(httpRequest(f, 'https://192.168.1.2:80/x', { method: 'GET' })).rejects.toMatchObject({ code: 'bad_host' });
    await expect(httpRequest(f, 'http://192.168.1.2:99999/x', { method: 'GET' })).rejects.toMatchObject({ code: 'bad_host' });
    expect(f).not.toHaveBeenCalled();
  });
});

describe('health contract', () => {
  it('asks for an update unless health says contract 1', async () => {
    for (const contract of [2, 0, undefined]) {
      const f = jest.fn(async () => ({ status: 200, text: async () => JSON.stringify({ status: 'ok', contract }) }));
      await expect(go(CREDS, f)).rejects.toMatchObject({ code: 'update_needed' });
    }
  });
});

describe('redirects and size limits', () => {
  it('never follows redirects and treats them as bad_response', async () => {
    const f = jest.fn(async () => ({ status: 302, headers: { get: () => 'http://evil.example/' }, text: async () => '' }));
    await expect(go(CREDS, f)).rejects.toMatchObject({ code: 'bad_response' });
    expect((f.mock.calls as unknown[][])[0][1]).toMatchObject({ redirect: 'manual' });
    const opaque = jest.fn(async () => ({ status: 0, type: 'opaqueredirect', text: async () => '' }));
    await expect(go(CREDS, opaque)).rejects.toMatchObject({ code: 'bad_response' });
  });

  it('rejects a declared Content-Length over the limit without reading the body', async () => {
    const text = jest.fn(async () => '{}');
    const f = jest.fn(async () => ({ status: 200, headers: { get: () => '99999' }, text }));
    await expect(go(CREDS, f)).rejects.toMatchObject({ code: 'something_wrong' });
    expect(text).not.toHaveBeenCalled();
  });

  it('counts real bytes, not characters, when it has to read the whole text', async () => {
    // 9,000 two-byte characters: 9,000 UTF-16 units but 18,000 bytes, over the 16 KiB limit.
    const f = jest.fn(async () => ({ status: 200, text: async () => 'é'.repeat(9000) }));
    await expect(go(CREDS, f)).rejects.toMatchObject({ code: 'something_wrong' });
  });

  it('stops reading a stream and aborts once the body is over the limit', async () => {
    let signal: AbortSignal | undefined;
    const cancel = jest.fn(async () => undefined);
    let reads = 0;
    const f = jest.fn(async (_u: string, init: { signal: AbortSignal }) => {
      signal = init.signal;
      return {
        status: 200,
        body: {
          getReader: () => ({
            read: async () => (++reads > 100 ? { done: true } : { done: false, value: new Uint8Array(1024) }),
            cancel,
          }),
        },
      };
    });
    await expect(go(CREDS, f as unknown as jest.Mock)).rejects.toMatchObject({ code: 'something_wrong' });
    expect(reads).toBeLessThan(20);
    expect(signal?.aborted).toBe(true);
    expect(cancel).toHaveBeenCalled();
  });

  it('reads a small streamed body fine', async () => {
    const bytes = new TextEncoder().encode('{"status":"ok","contract":2}');
    let sent = false;
    const f = jest.fn(async () => ({
      status: 200,
      body: {
        getReader: () => ({
          read: async () => (sent ? { done: true } : ((sent = true), { done: false, value: bytes })),
          cancel: async () => undefined,
        }),
      },
    }));
    await expect(go(CREDS, f)).rejects.toMatchObject({ code: 'update_needed' });
  });
});

describe('streaming without TextDecoder, and address checks', () => {
  it('decodes a streamed body (multi-byte characters split across chunks) with no TextDecoder', async () => {
    const original = globalThis.TextDecoder;
    (globalThis as { TextDecoder?: unknown }).TextDecoder = undefined;
    try {
      const bytes = new TextEncoder().encode('{"merchant":"Café Olé"}');
      const cut = bytes.indexOf(0xc3) + 1; // split in the middle of the first "é"
      const parts = [bytes.slice(0, cut), bytes.slice(cut)];
      let i = 0;
      const f = jest.fn(async () => ({
        status: 200,
        body: {
          getReader: () => ({
            read: async () => (i < parts.length ? { done: false, value: parts[i++] } : { done: true }),
            cancel: async () => undefined,
          }),
        },
      }));
      const res = await httpRequest(f as unknown as typeof fetch, 'http://192.168.1.2:8765/x', { method: 'GET' });
      expect(JSON.parse(res.text)).toEqual({ merchant: 'Café Olé' });
    } finally {
      globalThis.TextDecoder = original;
    }
  });

  it('accepts a bracketed private IPv6 URL and refuses a public one', async () => {
    const f = jest.fn(async () => ({ status: 200, text: async () => '{}' }));
    const get = (url: string) => httpRequest(f as unknown as typeof fetch, url, { method: 'GET' });
    await expect(get('http://[fd00::1]:8765/api/health')).resolves.toMatchObject({ status: 200 });
    await expect(get('http://[2001:db8::1]:8765/api/health')).rejects.toMatchObject({ code: 'bad_host' });
  });

  it('pairing refuses a public host in the transport itself', async () => {
    const qr = {
      v: 1,
      app: 'budget-buddy',
      host: '8.8.8.8',
      port: 8765,
      code: 'pQ3mX9vT2aLk8RzN1bWc4g',
      pair_pub: 'YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw',
      server_id: CREDS.server_id,
      name: 'x',
      exp: NOW + 600,
    };
    const f = jest.fn();
    await expect(
      pairWithComputer(qr, { deviceName: 'p', platform: 'ios', appVersion: '1.0.0' }, { fetch: f as unknown as typeof fetch, now: () => NOW }),
    ).rejects.toMatchObject({ code: 'bad_host' });
    expect(f).not.toHaveBeenCalled();
  });
});
