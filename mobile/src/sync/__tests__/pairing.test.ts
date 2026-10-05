import nacl from 'tweetnacl';

import { b64uDecode, b64uEncode } from '../base64url';
import { CREDENTIALS_KEY, loadCredentials, saveCredentials } from '../credentials';
import { pairWithComputer, PAIR_PATH } from '../pairClient';
import { PAIR_MESSAGES, PairError } from '../pairErrors';
import { isPrivateHost, parsePairingPayload } from '../pairingQr';

// Contract v1, section 4.7 (fixed test-only values).
const range = (a: number, b: number) => Uint8Array.from({ length: b - a + 1 }, (_, i) => a + i);
const PAIR_PUB = 'YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw';
const PHONE_PUB = 'ST6C_HRGSlkmiBdiPSBTxeuOLMSpiLT-4XnsawENUx0';
const SHARED = 'zSsDtyenL7oJQc53ndiVIG5KaKRYVTL4LHpaOqazn_c';
const SERVER_ID = 'Zk3pR7tQ1xYb9mWc2nLs5Q';
const VECTOR4_ENVELOPE = {
  v: 1,
  nonce: 'wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX',
  ts: 1790000000,
  phone_pub: PHONE_PUB,
  box: 'iX68iqmvSCofJGxoNa6ebGX424xYOa65Hp175w4pshg0QFxkfGk7IJSqHtBmtUmvZqsuM3uzkXYBVTevNr3Pt8LZmisOoF1RHF7bcQ1d01XIRobOmjXEr5AKOoJ9Gip52s6weSGEDbLZYnq9dE0HaO4Hb475qcwAQ_hrx_EpnEXBfJatjlr-W3-1-1XYBTtN9dOC9U12WfqBH76uDT23FI_1BTze3vUIbT3lBerNaXkQflETufHrnpuhaIUEeVvJzNi_A-2QmCAH',
};

const QR = {
  v: 1,
  app: 'budget-buddy',
  host: '192.168.1.20',
  port: 8765,
  code: 'pQ3mX9vT2aLk8RzN1bWc4g',
  pair_pub: PAIR_PUB,
  server_id: SERVER_ID,
  name: 'Home Base',
  exp: 1790000600,
};
const NOW = 1790000000;
const DEVICE = { deviceName: 'Test Phone', platform: 'ios' as const, appVersion: '1.0.0' };
const TOKEN = 'YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8';
const SYNC_KEY = '4OHi4-Tl5ufo6err7O3u7_Dx8vP09fb3-Pn6-_z9_v8';

const deps = (fetch: jest.Mock) => ({
  fetch: fetch as unknown as typeof globalThis.fetch,
  now: () => NOW,
  phoneSecretKey: range(0x80, 0x9f),
  nonce: range(0xc0, 0xd7),
});

/** What the server sends back: a box under `shared`, answering the request nonce. */
function serverReply(inner: object, key = b64uDecode(SHARED, 32)) {
  const nonce = range(0x40, 0x57);
  const pt = new TextEncoder().encode(JSON.stringify(inner));
  return { v: 1, nonce: b64uEncode(nonce), ts: NOW + 1, box: b64uEncode(nacl.secretbox(pt, nonce, key)) };
}
const okInner = (over: Record<string, unknown> = {}) => ({
  type: 'res',
  ts: NOW + 1,
  re: VECTOR4_ENVELOPE.nonce,
  status: 200,
  data: { device_id: 3, token: TOKEN, sync_key: SYNC_KEY, server_id: SERVER_ID, server_name: 'Home Base', ...over },
});
const respond = (body: unknown, status = 200) =>
  jest.fn().mockResolvedValue({ status, text: async () => JSON.stringify(body) });

describe('base64url (contract 4.6, vector 5)', () => {
  it.each([
    'Zk3pR7tQ1xYb9mWc2nLs5a',
    'ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3=',
    'ICEiIyQlJicoKSorLC0uLzAxMjM0NTY+',
    'AAAAA',
    'ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3\n',
  ])('rejects %j', (s) => expect(() => b64uDecode(s)).toThrow());

  it('rejects a wrong length and accepts the canonical form', () => {
    expect(() => b64uDecode('AAECAwQFBgcICQoLDA0ODxAREhMUFRYX', 32)).toThrow();
    expect(b64uDecode(SERVER_ID, 16)).toHaveLength(16);
  });
});

describe('QR checks (contract 2.1)', () => {
  it('accepts the contract example', () => {
    expect(parsePairingPayload(JSON.stringify(QR), NOW).host).toBe('192.168.1.20');
  });

  it.each([
    ['not JSON', 'hello'],
    ['another app', JSON.stringify({ ...QR, app: 'other' })],
    ['a missing field', JSON.stringify({ ...QR, code: undefined })],
    ['a short code', JSON.stringify({ ...QR, code: 'AAAA' })],
    ['a public IP', JSON.stringify({ ...QR, host: '8.8.8.8' })],
    ['a hostname', JSON.stringify({ ...QR, host: 'example.local' })],
  ])('refuses %s as invalid_qr', (_n, text) => {
    expect(() => parsePairingPayload(text, NOW)).toThrow(expect.objectContaining({ code: 'invalid_qr' }));
  });

  it('refuses unknown versions and expired codes', () => {
    expect(() => parsePairingPayload(JSON.stringify({ ...QR, v: 2 }), NOW)).toThrow(
      expect.objectContaining({ code: 'update_needed' }),
    );
    expect(() => parsePairingPayload(JSON.stringify(QR), QR.exp + 1)).toThrow(
      expect.objectContaining({ code: 'pairing_expired' }),
    );
  });

  it('allows only private, loopback and link-local IP literals', () => {
    for (const h of ['10.1.2.3', '172.16.0.1', '172.31.255.1', '192.168.0.9', '169.254.1.1', '127.0.0.1', '::1', 'fd12:3456::1', 'fe80::1', '::ffff:192.168.1.5']) {
      expect(isPrivateHost(h)).toBe(true);
    }
    for (const h of ['172.32.0.1', '11.0.0.1', '8.8.8.8', '2001:db8::1', '::ffff:8.8.8.8', '192.168.1', '010.0.0.1', 'localhost', '[::1]']) {
      expect(isPrivateHost(h)).toBe(false);
    }
  });
});

describe('pairWithComputer (mocked fetch, contract 3.6 and vector 4)', () => {
  it('sends exactly the contract envelope and returns the credentials', async () => {
    const fetch = respond(serverReply(okInner()));
    const creds = await pairWithComputer(QR, DEVICE, deps(fetch));

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`http://192.168.1.20:8765${PAIR_PATH}`);
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' }); // no Authorization
    expect(JSON.parse(init.body)).toEqual(VECTOR4_ENVELOPE);

    expect(creds).toEqual({
      host: '192.168.1.20',
      port: 8765,
      sync_key: SYNC_KEY,
      token: TOKEN,
      server_id: SERVER_ID,
      server_name: 'Home Base',
      device_id: 3,
    });
  });

  it('refuses an answer from a different computer (wrong_server)', async () => {
    const fetch = respond(serverReply(okInner({ server_id: 'AAECAwQFBgcICQoLDA0ODw' })));
    await expect(pairWithComputer(QR, DEVICE, deps(fetch))).rejects.toMatchObject({ code: 'wrong_server' });
  });

  it('refuses an answer that is not for this request (bad_response)', async () => {
    const wrongRe = respond(serverReply({ ...okInner(), re: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' }));
    await expect(pairWithComputer(QR, DEVICE, deps(wrongRe))).rejects.toMatchObject({ code: 'bad_response' });
    const wrongType = respond(serverReply({ ...okInner(), type: 'req' }));
    await expect(pairWithComputer(QR, DEVICE, deps(wrongType))).rejects.toMatchObject({ code: 'bad_response' });
    const wrongKey = respond(serverReply(okInner(), nacl.randomBytes(32)));
    await expect(pairWithComputer(QR, DEVICE, deps(wrongKey))).rejects.toMatchObject({ code: 'bad_response' });
  });

  it('refuses a token that is not 32 bytes (bad_response)', async () => {
    const fetch = respond(serverReply(okInner({ token: 'AAAA' })));
    await expect(pairWithComputer(QR, DEVICE, deps(fetch))).rejects.toMatchObject({ code: 'bad_response' });
  });

  it('maps an encrypted wrong-code answer to pairing_expired', async () => {
    const inner = { type: 'res', ts: NOW + 1, re: VECTOR4_ENVELOPE.nonce, status: 410, error: { code: 'pairing_expired', message: 'server text' } };
    const fetch = respond(serverReply(inner), 410);
    await expect(pairWithComputer(QR, DEVICE, deps(fetch))).rejects.toMatchObject({ code: 'pairing_expired' });
  });

  it.each([
    [429, 'too_many_attempts'],
    [410, 'pairing_expired'],
    [400, 'clock_skew'],
    [426, 'update_needed'],
    [403, 'not_home_network'],
    [403, 'bad_host'],
  ])('shows our own plain-English text for plaintext %i %s', async (status, code) => {
    const fetch = respond({ error: { code, message: 'SERVER WORDS', server_time: 1 } }, status);
    const err = await pairWithComputer(QR, DEVICE, deps(fetch)).catch((e) => e);
    expect(err).toBeInstanceOf(PairError);
    expect(err.code).toBe(code);
    expect(err.message).toBe(PAIR_MESSAGES[code as keyof typeof PAIR_MESSAGES]);
  });

  it('treats a plaintext 403 with no error body as not_home_network', async () => {
    const fetch = respond({ detail: 'Budget Buddy only answers devices on your home network.' }, 403);
    await expect(pairWithComputer(QR, DEVICE, deps(fetch))).rejects.toMatchObject({ code: 'not_home_network' });
  });

  it('says the computer cannot be reached when the network fails', async () => {
    const fetch = jest.fn().mockRejectedValue(new TypeError('Network request failed'));
    const err = await pairWithComputer(QR, DEVICE, deps(fetch)).catch((e) => e);
    expect(err.code).toBe('server_unreachable');
    expect(err.message).toContain('home Wi-Fi');
  });

  it('uses a fresh keypair and nonce each time when none are injected', async () => {
    const fetch = respond({ error: { code: 'pairing_expired' } }, 410);
    const d = { fetch: fetch as unknown as typeof globalThis.fetch, now: () => NOW };
    await pairWithComputer(QR, DEVICE, d).catch(() => undefined);
    await pairWithComputer(QR, DEVICE, d).catch(() => undefined);
    const [a, b] = fetch.mock.calls.map((c) => JSON.parse(c[1].body));
    expect(a.phone_pub).not.toBe(b.phone_pub);
    expect(a.nonce).not.toBe(b.nonce);
  });
});

describe('timeouts and size limits', () => {
  it('times out if the body arrives too slowly', async () => {
    jest.useFakeTimers();
    try {
      const fetch = jest.fn().mockResolvedValue({ status: 200, text: () => new Promise(() => undefined) });
      const p = pairWithComputer(QR, DEVICE, deps(fetch)).catch((e) => e);
      await jest.advanceTimersByTimeAsync(10_001);
      expect((await p).code).toBe('server_unreachable');
    } finally {
      jest.useRealTimers();
    }
  });

  it('refuses a body over 16 KiB without parsing it', async () => {
    const fetch = jest.fn().mockResolvedValue({ status: 200, text: async () => 'x'.repeat(16 * 1024 + 1) });
    await expect(pairWithComputer(QR, DEVICE, deps(fetch))).rejects.toMatchObject({ code: 'something_wrong' });
  });
});

describe('credentials', () => {
  it('round-trips through the secure store', async () => {
    const c = { host: '192.168.1.20', port: 8765, sync_key: SYNC_KEY, token: TOKEN, server_id: SERVER_ID, server_name: 'Home Base', device_id: 3 };
    expect(await loadCredentials()).toBeNull();
    await saveCredentials(c);
    expect(await loadCredentials()).toEqual(c);
    expect(CREDENTIALS_KEY).toMatch(/^[A-Za-z0-9._-]+$/); // valid secure-store key
  });
});
