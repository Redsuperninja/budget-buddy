// Backups (ADR-0012): which key made a backup file (from its first bytes, without uploading it) and the
// plain words for a waiting restore. No page code, so it's tested with node --test.

const MAGIC = [0x42, 0x42, 0x4b]; // "BBK"

// The key fingerprint (32 hex characters) in a backup file's first 36 bytes, or null if it isn't one.
export function fingerprintOf(bytes) {
  if (bytes.length < 36 || MAGIC.some((b, i) => bytes[i] !== b)) return null;
  return Array.from(bytes.slice(4, 20), (b) => b.toString(16).padStart(2, "0")).join("");
}

// "made 2026-10-16 at 14:05, with 3 receipt photos" for a waiting restore ({ made, receipts }).
export function describeBackup({ made, receipts }) {
  const when = Number.isFinite(made) ? new Date(made * 1000) : null;
  const date = when ? `made ${when.toISOString().slice(0, 10)} at ${when.toTimeString().slice(0, 5)}` : "made on an unknown date";
  const count = Number.isInteger(receipts) && receipts >= 0 ? receipts : 0;
  return `${date}, with ${count} receipt photo${count === 1 ? "" : "s"}`;
}
