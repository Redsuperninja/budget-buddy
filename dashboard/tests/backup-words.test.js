// Backups: reading which key made a file, and the words for a waiting restore.

import assert from "node:assert/strict";
import test from "node:test";

import { describeBackup, fingerprintOf } from "../js/backup-words.js";

const header = (magic = [0x42, 0x42, 0x4b]) =>
  Uint8Array.from([...magic, 1, ...Array.from({ length: 16 }, (_, i) => i), ...new Array(16).fill(0)]);

test("fingerprintOf reads the 16 key bytes after the magic and version", () => {
  assert.equal(fingerprintOf(header()), "000102030405060708090a0b0c0d0e0f");
});

test("fingerprintOf says null for anything that isn't a backup", () => {
  assert.equal(fingerprintOf(header([0x50, 0x4b, 0x03])), null); // a zip file
  assert.equal(fingerprintOf(Uint8Array.from([0x42, 0x42, 0x4b])), null); // too short
});

test("describeBackup gives the date and the receipt count in plain words", () => {
  const made = Date.UTC(2026, 9, 16, 12) / 1000;
  assert.match(describeBackup({ made, receipts: 3 }), /^made 2026-10-16 at \d\d:\d\d, with 3 receipt photos$/);
  assert.match(describeBackup({ made, receipts: 1 }), /with 1 receipt photo$/);
  assert.equal(describeBackup({ made: null, receipts: "x" }), "made on an unknown date, with 0 receipt photos");
});
