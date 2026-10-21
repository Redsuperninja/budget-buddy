// Switches for things that aren't ready for everyone yet, and what this device can show.

// The Expo phone app isn't published to the app stores yet (docs/dev/release.md). While false, the simple view and
// Home's Get started offer only the browser way (ADR-0009). Set to true when the app is published.
export const PHONE_APP_PUBLISHED = false;

// Connecting phones and computers only works on the Budget Buddy computer itself.
export const onThisComputer = (hostname = globalThis.location?.hostname) =>
  ["127.0.0.1", "localhost", "[::1]"].includes(hostname);

// The pages of the Devices section. Without the published app, "Connect phone" is an All tools page and the
// Devices section opens on "Other devices" (the browser way).
export function devicePages(load, phoneAppPublished = PHONE_APP_PUBLISHED) {
  const phone = { id: "phone", label: "Connect phone", load: load.phone, advanced: !phoneAppPublished };
  const computers = { id: "computers", label: "Other devices", load: load.computers };
  const backups = { id: "backups", label: "Backups", load: load.backups };
  return phoneAppPublished ? [phone, computers, backups] : [computers, phone, backups];
}

// Links for Get started's optional phone step: [href, text] pairs, or null when no step makes sense. Pairing and
// the one-time codes exist only on the Budget Buddy computer, so a joined phone or computer gets no step.
export function phoneStepLinks({ onThisComputer: here, phoneAppPublished = PHONE_APP_PUBLISHED }) {
  if (!here) return null;
  const links = [["#computers", "open it in your phone's web browser"]];
  if (phoneAppPublished) links.unshift(["#phone", "Connect the phone app"]);
  return links;
}
