/** Strict base64url without padding (sync contract v1, section 4.6). */
import { decodeBase64, encodeBase64 } from 'tweetnacl-util';

const B64U = /^[A-Za-z0-9_-]*$/;

export const b64uEncode = (b: Uint8Array): string =>
  encodeBase64(b).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export function b64uDecode(s: string, expectedLength?: number): Uint8Array {
  if (typeof s !== 'string' || !B64U.test(s) || s.length % 4 === 1) throw new Error('not base64url');
  const std = s.replace(/-/g, '+').replace(/_/g, '/');
  const bytes = decodeBase64(std + '='.repeat((4 - (std.length % 4)) % 4));
  if (b64uEncode(bytes) !== s) throw new Error('non-canonical base64url');
  if (expectedLength !== undefined && bytes.length !== expectedLength) throw new Error('wrong length');
  return bytes;
}
