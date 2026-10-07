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

export const date = (v: unknown, p: string) => matching(v, ISO_DATE, p, 'a date like 2026-10-02');

export function oneOf<T extends string | number>(v: unknown, allowed: readonly T[], path: string): T {
  if (!allowed.includes(v as T)) {
    throw new SnapshotError(path, `expected one of ${allowed.join(', ')}`);
  }
  return v as T;
}
