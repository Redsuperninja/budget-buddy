// The Simple / All tools choice: parsing, saving (even when storage is blocked), and applying it.

import assert from "node:assert/strict";
import test from "node:test";

import { VIEWS, applyView, loadView, parseView, saveView } from "../js/view.js";

function fakeStorage() {
  const items = new Map();
  return { getItem: (k) => (items.has(k) ? items.get(k) : null), setItem: (k, v) => items.set(k, v) };
}

function fakeRoot() {
  const attrs = new Map();
  return { attrs, setAttribute: (k, v) => attrs.set(k, v), removeAttribute: (k) => attrs.delete(k) };
}

test("parseView keeps known choices and turns anything else into simple", () => {
  for (const [value] of VIEWS) assert.equal(parseView(value), value);
  for (const bad of [null, undefined, "", "ALL", "expert"]) assert.equal(parseView(bad), "simple");
});

test("a saved view comes back; nothing saved means simple", () => {
  const storage = fakeStorage();
  assert.equal(loadView(storage), "simple");
  saveView(storage, "all");
  assert.equal(loadView(storage), "all");
});

test("the view is kept apart from the color choice", () => {
  const storage = fakeStorage();
  saveView(storage, "all");
  assert.equal(storage.getItem("budget-buddy-theme"), null);
});

test("applyView sets data-view for All tools and removes it for simple", () => {
  const root = fakeRoot();
  applyView(root, "all");
  assert.equal(root.attrs.get("data-view"), "all");
  applyView(root, "simple");
  assert.equal(root.attrs.has("data-view"), false);
});
