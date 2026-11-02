// Home's gentle backup reminder: shown on this computer when the last backup is over 30 days old, or there has
// never been one and there is data worth keeping. "Remind me later" hides it for a week. The Home Base's setup
// record has no field for that, so the choice is kept in this browser's localStorage (so the desktop window and a
// browser on the same computer each remember their own).

import { daysBetween, localDate, today } from "../../dates.js";
import { browserStorage, h } from "../../dom.js";
import { reload } from "../../router.js";

export const REMIND_AFTER_DAYS = 30;
export const SNOOZE_DAYS = 7;
export const SNOOZE_KEY = "backup-reminder-until";

// Whether to remind, and how to word it. setup: GET /api/local/setup or null; hasData: any account or transaction;
// snoozedUntil: "YYYY-MM-DD" or null; day: today's "YYYY-MM-DD". Returns the sentence, or null for no reminder.
export function reminderText(setup, hasData, snoozedUntil, day = today()) {
  if (!setup || !hasData) return null;
  if (snoozedUntil && day < snoozedUntil) return null;
  if (!setup.last_backup_at) return "You haven't made a backup yet.";
  const age = daysBetween(localDate(setup.last_backup_at), day);
  return age > REMIND_AFTER_DAYS ? `Your last backup was ${age} days ago.` : null;
}

export function snoozeDate(day = today()) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + SNOOZE_DAYS);
  return d.toISOString().slice(0, 10);
}

function readSnooze(storage) {
  try {
    return storage?.getItem(SNOOZE_KEY) || null;
  } catch {
    return null;
  }
}

export function backupReminder(setup, hasData, storage = browserStorage()) {
  const text = reminderText(setup, hasData, readSnooze(storage));
  if (!text) return null;
  const later = h("button", { type: "button" }, "Remind me later");
  later.addEventListener("click", () => {
    try {
      storage?.setItem(SNOOZE_KEY, snoozeDate());
    } catch {
      /* storage turned off: the reminder returns next time Home opens */
    }
    reload();
  });
  return h("div", { class: "note", role: "region", "aria-label": "Backup reminder" },
    h("p", {}, `${text} A backup protects your data if this computer is lost or breaks. `,
      h("a", { href: "#backups" }, "Make a backup")),
    later);
}
