import { test } from "node:test";
import assert from "node:assert/strict";

import { plural, washSales } from "../js/plural.js";

test("a count with its noun", () => {
  assert.equal(plural(1, "paycheck"), "1 paycheck");
  assert.equal(plural(0, "paycheck"), "0 paychecks");
  assert.equal(plural(5, "new row"), "5 new rows");
  assert.equal(plural(2, "category", "categories"), "2 categories");
});

test("wash sales agree with their count", () => {
  assert.equal(washSales(1), "1 sale may be a wash sale.");
  assert.equal(washSales(3), "3 sales may be wash sales.");
});

test("no screen writes (s) any more", async () => {
  const { readdirSync, readFileSync, statSync } = await import("node:fs");
  const { join } = await import("node:path");
  const walk = (dir) => readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : p.endsWith(".js") ? [p] : [];
  });
  const bad = walk(new URL("../js", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1"))
    .filter((p) => !p.endsWith("plural.js") && /\b[a-z]+\(s\)/.test(readFileSync(p, "utf8")));
  assert.deepEqual(bad, []);
});
