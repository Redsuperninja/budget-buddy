// The light/dark choice: parsing, saving (even when storage is blocked), and applying it.

import assert from "node:assert/strict";
import test from "node:test";

import { THEMES, applyTheme, loadTheme, parseTheme, saveTheme } from "../js/theme.js";

function fakeStorage() {
  const items = new Map();
  return { getItem: (k) => (items.has(k) ? items.get(k) : null), setItem: (k, v) => items.set(k, v) };
}

const blocked = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };

function fakeRoot() {
  const attrs = new Map();
  return { attrs, setAttribute: (k, v) => attrs.set(k, v), removeAttribute: (k) => attrs.delete(k) };
}

test("parseTheme keeps known choices and turns anything else into system", () => {
  for (const [value] of THEMES) assert.equal(parseTheme(value), value);
  for (const bad of [null, undefined, "", "blue", "DARK"]) assert.equal(parseTheme(bad), "system");
});

test("a saved choice comes back; nothing saved means system", () => {
  const storage = fakeStorage();
  assert.equal(loadTheme(storage), "system");
  saveTheme(storage, "dark");
  assert.equal(loadTheme(storage), "dark");
  saveTheme(storage, "nonsense");
  assert.equal(loadTheme(storage), "system");
});

test("blocked or missing storage never throws", () => {
  assert.equal(loadTheme(blocked), "system");
  assert.equal(loadTheme(null), "system");
  saveTheme(blocked, "dark");
  saveTheme(null, "dark");
});

test("applyTheme sets data-theme for light and dark, and removes it for system", () => {
  const root = fakeRoot();
  applyTheme(root, "dark");
  assert.equal(root.attrs.get("data-theme"), "dark");
  applyTheme(root, "light");
  assert.equal(root.attrs.get("data-theme"), "light");
  applyTheme(root, "system");
  assert.equal(root.attrs.has("data-theme"), false);
});
