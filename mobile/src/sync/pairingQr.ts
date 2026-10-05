/** Reads and checks the pairing QR payload (sync contract v1, section 2.1). */
import { b64uDecode } from './base64url';
import { PairError } from './pairErrors';

export const CONTRACT_VERSION = 1;

export type PairingPayload = {
  v: number;
  app: string;
  host: string;
  port: number;
  code: string;
  pair_pub: string;
  server_id: string;
  name: string;
  exp: number;
};

function parseIPv4(s: string): number[] | null {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(s);
  if (!m) return null;
  const parts = m.slice(1).map((p) => (p.length > 1 && p.startsWith('0') ? NaN : Number(p)));
  return parts.every((n) => Number.isInteger(n) && n >= 0 && n <= 255) ? parts : null;
}

function isPrivateV4(p: number[]): boolean {
  const [a, b] = p;
  return (
    a === 127 ||
    a === 10 ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 169 && b === 254)
  );
}

/** Expand an IPv6 literal (no brackets, no zone) into 8 16-bit groups, or null if malformed. */
function parseIPv6(s: string): number[] | null {
  if (!/^[0-9a-fA-F:.]+$/.test(s) || !s.includes(':')) return null;
  let text = s;
  let tail: number[] = [];
  if (s.includes('.')) {
    const v4 = parseIPv4(s.slice(s.lastIndexOf(':') + 1));
    if (!v4) return null;
    tail = [(v4[0] << 8) | v4[1], (v4[2] << 8) | v4[3]];
    text = s.slice(0, s.lastIndexOf(':') + 1) + '0:0'; // placeholders, replaced below
  }
  const halves = text.split('::');
  if (halves.length > 2) return null;
  const toGroups = (h: string) => (h === '' ? [] : h.split(':'));
  const head = toGroups(halves[0]);
  const rest = halves.length === 2 ? toGroups(halves[1]) : [];
  if (![...head, ...rest].every((g) => /^[0-9a-fA-F]{1,4}$/.test(g))) return null;
  const missing = 8 - head.length - rest.length;
  if (halves.length === 2 ? missing < 1 : missing !== 0) return null;
  const groups = [...head, ...Array<string>(halves.length === 2 ? missing : 0).fill('0'), ...rest].map(
    (g) => parseInt(g, 16),
  );
  if (tail.length) groups.splice(6, 2, ...tail);
  return groups;
}

/** True only for loopback, private (RFC1918 / unique local) and link-local IP literals, like the server. */
export function isPrivateHost(host: unknown): boolean {
  if (typeof host !== 'string') return false;
  const v4 = parseIPv4(host);
  if (v4) return isPrivateV4(v4);
  const g = parseIPv6(host);
  if (!g) return false;
  if (g.slice(0, 5).every((x) => x === 0) && g[5] === 0xffff) {
    return isPrivateV4([g[6] >> 8, g[6] & 255, g[7] >> 8, g[7] & 255]); // IPv4-mapped
  }
  if (g.slice(0, 7).every((x) => x === 0) && g[7] === 1) return true; // ::1
  if ((g[0] & 0xfe00) === 0xfc00) return true; // fc00::/7
  if ((g[0] & 0xffc0) === 0xfe80) return true; // fe80::/10
  return false;
}

export function baseUrl(host: string, port: number): string {
  return host.includes(':') ? `http://[${host}]:${port}` : `http://${host}:${port}`;
}

/**
 * Parse the text from the QR (or typed in) and check it. Throws PairError:
 * `invalid_qr`, `update_needed` (unknown version) or `pairing_expired`.
 */
export function parsePairingPayload(text: string, nowSeconds: number): PairingPayload {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new PairError('invalid_qr');
  }
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) throw new PairError('invalid_qr');
  const o = raw as Record<string, unknown>;
  if (o.app !== 'budget-buddy') throw new PairError('invalid_qr');
  if (typeof o.v !== 'number' || !Number.isInteger(o.v)) throw new PairError('invalid_qr');
  if (o.v !== CONTRACT_VERSION) throw new PairError('update_needed');
  const { host, port, code, pair_pub, server_id, name, exp } = o;
  if (
    typeof host !== 'string' ||
    typeof code !== 'string' ||
    typeof pair_pub !== 'string' ||
    typeof server_id !== 'string' ||
    typeof name !== 'string' ||
    typeof port !== 'number' ||
    !Number.isInteger(port) ||
    port < 1 ||
    port > 65535 ||
    typeof exp !== 'number' ||
    !Number.isInteger(exp)
  ) {
    throw new PairError('invalid_qr');
  }
  try {
    b64uDecode(pair_pub, 32);
    b64uDecode(code, 16);
    b64uDecode(server_id, 16);
  } catch {
    throw new PairError('invalid_qr');
  }
  if (!isPrivateHost(host)) throw new PairError('invalid_qr');
  if (exp <= nowSeconds) throw new PairError('pairing_expired');
  return { v: o.v, app: 'budget-buddy', host, port, code, pair_pub, server_id, name: name.slice(0, 50), exp };
}
