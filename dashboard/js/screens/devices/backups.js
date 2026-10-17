// Backups (ADR-0012): download one encrypted backup file, or pick one to restore. A restore is checked
// now and finished the next time Budget Buddy starts. A file made on another computer needs the
// recovery phrase. Only on the Budget Buddy computer.

import { backupFileUrl, backupStatus, cancelRestore, startRestore } from "../../api/endpoints.js";
import { describeBackup, fingerprintOf } from "../../backup-words.js";
import { fill, h, showError } from "../../dom.js";
import { card, empty, note } from "../../widgets.js";

const RESTART = "To finish, close Budget Buddy and start it again. Your data is replaced then, not before.";

function waitingRestore(status, refresh) {
  if (!status.pending) return null;
  const box = h("div", {});
  const cancel = h("button", { type: "button", onclick: async () => {
    cancel.disabled = true;
    try {
      await cancelRestore();
      await refresh();
    } catch (err) {
      cancel.disabled = false;
      showError(box, err);
    }
  } }, "Cancel the restore");
  return card("A restore is waiting",
    h("p", { role: "status" }, `A backup ${describeBackup(status.pending)} is checked and ready.`),
    note(RESTART), cancel, box);
}

function restoreCard(status, refresh) {
  const fileInput = h("input", { type: "file", accept: ".bbbackup" });
  const phraseBox = h("div", {});
  const result = h("div", {});
  let phraseInput = null; // shown only for a backup made with another key

  async function restore() {
    if (!fileInput.files.length) throw new Error("Please choose a backup file first.");
    const file = fileInput.files[0];
    const made = fingerprintOf(new Uint8Array(await file.slice(0, 36).arrayBuffer()));
    if (!made) throw new Error("That isn't a Budget Buddy backup file. Its name ends in .bbbackup.");
    const otherKey = made !== status.key_fingerprint;
    if (otherKey && !phraseInput) {
      phraseInput = h("input", { type: "password", autocomplete: "off", spellcheck: "false", size: 60 });
      fill(phraseBox,
        note("This backup was made on another computer (or before a new key). Type its recovery phrase: " +
          "the words you saved when Budget Buddy was first set up there."),
        h("label", {}, "Recovery phrase ", phraseInput));
      phraseInput.focus();
      return;
    }
    const phrase = otherKey ? phraseInput.value.trim() : null;
    if (otherKey && !phrase) throw new Error("Please type the recovery phrase.");
    if (!confirm("Replace everything in Budget Buddy with this backup the next time it starts? " +
      "Your current data is kept in a separate folder, not deleted.")) return;
    await startRestore(file, phrase);
    await refresh();
  }

  fileInput.addEventListener("change", () => { phraseInput = null; fill(phraseBox); fill(result); });
  const button = h("button", { class: "primary", type: "button", onclick: async () => {
    button.disabled = true;
    try {
      await restore();
    } catch (err) {
      showError(result, err);
    } finally {
      button.disabled = false;
    }
  } }, "Restore this backup");
  return card("Restore from a backup",
    h("p", {}, "Pick a backup file to bring back everything in it. Budget Buddy checks the whole file first; " +
      "nothing changes until the next start."),
    h("label", {}, "Backup file ", fileInput), phraseBox, button, result);
}

export async function render(root) {
  async function refresh() {
    const status = await backupStatus();
    fill(root,
      status.restored_from
        ? h("p", { class: "ok", role: "status" }, `Restore finished. Your earlier data was kept in ${status.restored_from}.`)
        : null,
      card("Make a backup",
        h("p", {}, "Download one file with all your data and receipt photos, encrypted. Keep it somewhere " +
          "safe, like a USB drive. It can only be opened by this computer or with your recovery phrase."),
        h("a", { class: "button", href: backupFileUrl(), download: "" }, "Download a backup"),
        empty("Making the file can take a minute if you have many receipt photos.")),
      waitingRestore(status, refresh),
      status.pending ? null : restoreCard(status, refresh));
  }
  await refresh();
}
