// The About links: in the Windows window they go to the system browser; in a normal browser they are plain links.

import assert from "node:assert/strict";
import test from "node:test";

import { openInSystemBrowser } from "../js/about.js";

const click = () => ({ prevented: false, preventDefault() { this.prevented = true; } });

test("in a normal browser the link is left alone", () => {
  const event = click();
  assert.equal(openInSystemBrowser(event, "https://x", {}), false);
  assert.equal(event.prevented, false);
});

test("in the Windows window the click goes to the app, not the window", () => {
  const seen = [];
  const win = { pywebview: { api: { open_link: (url) => { seen.push(url); return Promise.resolve(); } } } };
  const event = click();
  assert.equal(openInSystemBrowser(event, "https://x", win), true);
  assert.equal(event.prevented, true);
  assert.deepEqual(seen, ["https://x"]);
});

test("a failing open does not break the page", () => {
  const win = { pywebview: { api: { open_link: () => Promise.reject(new Error("no")) } } };
  assert.equal(openInSystemBrowser(click(), "https://x", win), true);
});
