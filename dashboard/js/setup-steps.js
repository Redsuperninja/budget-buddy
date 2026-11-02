// When the Setup page is offered, and which of its steps are done (ADR-0015). Pure: no page, no network.

export const SKIPPED_KEY = "budget-buddy-setup-skipped"; // sessionStorage: "Finish later" was pressed

// Only on the Budget Buddy computer, only on a first visit to Home, only while setup isn't finished and there is
// no data yet. Anyone with accounts or transactions is never sent there.
// progress: { finished_at } from the Home Base. have: { accounts, transactions } counts. skipped: "Finish later" was
// pressed in this browser session.
export function shouldShowSetup({ onThisComputer, hash, progress, have, skipped = false }) {
  if (!onThisComputer || skipped) return false;
  if (!["", "#", "#home"].includes(hash)) return false;
  if (!progress || progress.finished_at) return false;
  return have.accounts === 0 && have.transactions === 0;
}

// Which steps show a "Done" mark.
export const stepsDone = (progress, have) => ({
  phrase: Boolean(progress?.phrase_saved_at),
  account: have.accounts > 0 || have.transactions > 0,
});
