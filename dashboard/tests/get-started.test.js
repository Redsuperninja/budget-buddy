// Get started's recovery phrase and backup steps, and Home's backup reminder (the pure parts).

import assert from "node:assert/strict";
import test from "node:test";

import { REMIND_AFTER_DAYS, reminderText, snoozeDate } from "../js/screens/home/home-backup.js";
import { safetyOpen } from "../js/screens/home/home-start.js";

test("the safety steps stay open until the phrase is saved and a backup exists", () => {
  assert.equal(safetyOpen(null), false);
  assert.equal(safetyOpen({ phrase_saved_at: null, last_backup_at: "2026-10-01T10:00:00" }), true);
  assert.equal(safetyOpen({ phrase_saved_at: "2026-10-01T10:00:00", last_backup_at: null }), true);
  assert.equal(safetyOpen({ phrase_saved_at: "2026-10-01T10:00:00", last_backup_at: "2026-10-01T10:00:00" }), false);
});

test("no reminder on a joined device, with no data, or inside 30 days", () => {
  const recent = { last_backup_at: "2026-10-10T12:00:00" };
  assert.equal(reminderText(null, true, null, "2026-10-20"), null);
  assert.equal(reminderText({ last_backup_at: null }, false, null, "2026-10-20"), null);
  assert.equal(reminderText(recent, true, null, "2026-10-20"), null);
  assert.equal(REMIND_AFTER_DAYS, 30);
});

test("reminds when never backed up, or when the last backup is over 30 days old", () => {
  assert.match(reminderText({ last_backup_at: null }, true, null, "2026-10-20"), /haven't made a backup/);
  assert.match(reminderText({ last_backup_at: "2026-08-01T12:00:00" }, true, null, "2026-10-20"), /80 days ago/);
  assert.equal(reminderText({ last_backup_at: "2026-09-20T12:00:00" }, true, null, "2026-10-20"), null);
});

test("Remind me later hides the reminder for a week", () => {
  const setup = { last_backup_at: null };
  assert.equal(snoozeDate("2026-10-28"), "2026-11-04");
  assert.equal(reminderText(setup, true, "2026-10-27", "2026-10-20"), null);
  assert.notEqual(reminderText(setup, true, "2026-10-27", "2026-10-27"), null);
});
