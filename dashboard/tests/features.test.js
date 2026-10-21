// The phone-app switch and the Get started phone step on joined devices.

import assert from "node:assert/strict";
import test from "node:test";

import { PHONE_APP_PUBLISHED, devicePages, onThisComputer, phoneStepLinks } from "../js/features.js";

const load = { phone: () => 1, computers: () => 2, backups: () => 3 };

test("the phone app is marked as not published yet", () => {
  assert.equal(PHONE_APP_PUBLISHED, false);
});

test("a joined phone or computer gets no phone step (its pages don't exist there)", () => {
  assert.equal(phoneStepLinks({ onThisComputer: false }), null);
  assert.equal(phoneStepLinks({ onThisComputer: false, phoneAppPublished: true }), null);
});

test("on the Budget Buddy computer, only the browser way is offered until the app is published", () => {
  assert.deepEqual(phoneStepLinks({ onThisComputer: true }).map(([href]) => href), ["#computers"]);
  assert.deepEqual(phoneStepLinks({ onThisComputer: true, phoneAppPublished: true }).map(([href]) => href),
    ["#phone", "#computers"]);
});

test("Connect phone is an All tools page, and Devices opens on Other devices, until the app is published", () => {
  const pages = devicePages(load, false);
  assert.equal(pages[0].id, "computers");
  assert.equal(pages.find((p) => p.id === "phone").advanced, true);
  const published = devicePages(load, true);
  assert.equal(published[0].id, "phone");
  assert.equal(published[0].advanced, false);
});

test("onThisComputer recognises the local addresses only", () => {
  for (const host of ["127.0.0.1", "localhost", "[::1]"]) assert.equal(onThisComputer(host), true);
  assert.equal(onThisComputer("192.168.1.20"), false);
});
