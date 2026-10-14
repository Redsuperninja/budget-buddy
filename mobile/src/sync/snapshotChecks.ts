/** Small checks used to validate untrusted snapshot JSON. Each throws a SnapshotError naming the bad field. */

export class SnapshotError extends Error {
  constructor(readonly path: string, readonly problem: string) {
    super(`${path}: ${problem}`);
  }
}

export type Obj = Record<string, unknown>;

export const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
export const MONTH = /^\d{4}-\d{2}$/;
// RFC 3339: date, time, optional fraction, then Z or an offset.
export const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
export const CURRENCY = /^[A-Z]{3}$/;
export const SERVER_ID = /^[A-Za-z0-9_-]{1,64}$/; // base64url, like the Home Base's 16-byte ID

/**
 * Sizes a snapshot may not go past (contract §5.1 sets transactions and descriptions; the rest are
 * generous caps), so a buggy Home Base or a damaged saved copy can't freeze the screen. A saved copy
 * longer than `storedChars` isn't even read: Android can't read back a value of about 2 MB.
 */
export const SNAPSHOT_LIMITS = {
  storedChars: 512 * 1024,
  transactions: 500,
  accounts: 1000, // contract §5.1: the phone may refuse more
  categoriesPerGroup: 1000,
  deductions: 50,
  text: 100, // names, labels, descriptions
  disclaimer: 500,
} as const;

// Control characters (C0, C1), direction marks and overrides (U+061C, U+200E-200F, U+202A-202E,
// U+2066-2069) and line/paragraph separators (U+2028-2029): shown as a space, like the Home Base's bank-file
// import does (server/app/services/imports/csv_parsing.py _CONTROL; keep the two lists the same).
const HIDDEN_CHARS = /[\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069]/g;

export function obj(v: unknown, path: string): Obj {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) {
    throw new SnapshotError(path, 'expected an object');
  }
  return v as Obj;
}

export function arr(v: unknown, path: string): unknown[] {
  if (!Array.isArray(v)) throw new SnapshotError(path, 'expected a list');
  return v;
}

export function str(v: unknown, path: string): string {
  if (typeof v !== 'string') throw new SnapshotError(path, 'expected text');
  return v;
}

/** Text shown on screen: at most `max` characters, with control and direction-changing characters dropped. */
export function text(v: unknown, path: string, max: number = SNAPSHOT_LIMITS.text): string {
  const s = str(v, path);
  // Counted like the Home Base does (one per character, so an emoji is one, not two).
  if ([...s].length > max) throw new SnapshotError(path, `expected at most ${max} characters`);
  return s.replace(HIDDEN_CHARS, ' ').replace(/ {2,}/g, ' ').trim();
}

/** A list of at most `max` items. */
export function list(v: unknown, path: string, max: number): unknown[] {
  const a = arr(v, path);
  if (a.length > max) throw new SnapshotError(path, `expected at most ${max} items`);
  return a;
}

export function bool(v: unknown, path: string): boolean {
  if (typeof v !== 'boolean') throw new SnapshotError(path, 'expected true/false');
  return v;
}

export function int(v: unknown, path: string): number {
  if (typeof v !== 'number' || !Number.isSafeInteger(v)) {
    throw new SnapshotError(path, 'expected a whole number');
  }
  return v;
}

export function nonNegInt(v: unknown, path: string): number {
  const n = int(v, path);
  if (n < 0) throw new SnapshotError(path, 'expected zero or more');
  return n;
}

export function matching(v: unknown, re: RegExp, path: string, what: string): string {
  const s = str(v, path);
  if (!re.test(s)) throw new SnapshotError(path, `expected ${what}`);
  return s;
}

/** A real calendar date like 2026-10-02 (not 2026-02-30). Any year, even one before 100. */
export function date(v: unknown, p: string): string {
  const s = matching(v, ISO_DATE, p, 'a date like 2026-10-02');
  const [y, m, d] = s.split('-').map(Number);
  const real = new Date(0);
  real.setUTCFullYear(y, m - 1, d); // unlike Date.UTC, doesn't read years 0-99 as 1900-1999
  if (real.getUTCFullYear() !== y || real.getUTCMonth() !== m - 1 || real.getUTCDate() !== d) {
    throw new SnapshotError(p, 'expected a real date');
  }
  return s;
}

export function oneOf<T extends string | number>(v: unknown, allowed: readonly T[], path: string): T {
  if (!allowed.includes(v as T)) {
    throw new SnapshotError(path, `expected one of ${allowed.join(', ')}`);
  }
  return v as T;
}
