import { test } from "node:test";
import assert from "node:assert/strict";

import { saveWithNote } from "../js/form.js";

function fakeNote() {
  const attrs = {};
  return { textContent: "", attrs, setAttribute: (k, v) => { attrs[k] = v; } };
}

test("the note is a polite live region so a screen reader announces it", async () => {
  const note = fakeNote();
  await saveWithNote(note, async () => {});
  assert.equal(note.textContent, " Saved");
  assert.equal(note.attrs.role, "status");
  assert.equal(note.attrs["aria-live"], "polite");
});

test("a failed save shows the problem in the same note", async () => {
  const note = fakeNote();
  await saveWithNote(note, async () => { throw new Error("That name is taken."); });
  assert.equal(note.textContent, " That name is taken.");
});
