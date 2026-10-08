// Safety rules for every dashboard file, checked by reading the files (no browser needed).
// The server's own tests check the other half: headers, the CSRF token swap and what it serves.

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function listFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? listFiles(path) : [path];
  });
}

// The same files the server serves: index.html, top-level *.css, and js/**/*.js.
const served = [
  join(ROOT, "index.html"),
  ...readdirSync(ROOT).filter((f) => f.endsWith(".css")).map((f) => join(ROOT, f)),
  ...listFiles(join(ROOT, "js")).filter((f) => f.endsWith(".js")),
];
const scripts = served.filter((f) => f.endsWith(".js"));
const read = (file) => readFileSync(file, "utf8");
const name = (file) => relative(ROOT, file).replaceAll("\\", "/");

test("no file asks the internet for anything", () => {
  for (const file of served) {
    assert.doesNotMatch(read(file), /https?:\/\/|@import|url\(|["'`(=]\/\/[\w.-]/, name(file));
  }
});

const DANGEROUS = [
  /innerHTML/, /outerHTML/, /insertAdjacentHTML/, /document\.write/, /eval\(/, /new\s+Function/,
  /(setTimeout|setInterval)\(\s*["'`]/, /srcdoc/,
];

test("no file builds HTML from text or runs text as code", () => {
  for (const file of served) {
    for (const rule of DANGEROUS) assert.doesNotMatch(read(file), rule, name(file));
  }
});

test("the page has no inline event handlers", () => {
  assert.doesNotMatch(read(join(ROOT, "index.html")), /\son[a-z]+\s*=/i);
});

test("screens fill through fill(), which skips empty parts", () => {
  // el.replaceChildren(null) would show the word "null" on the page.
  for (const file of scripts) assert.ok(!read(file).includes("replaceChildren("), name(file));
});

test("the page has no inline script or style, and loads main.js", () => {
  const html = read(join(ROOT, "index.html"));
  assert.doesNotMatch(html, /<script(?![^>]*\bsrc=)/);
  assert.ok(!html.includes(" style=") && !html.includes("<style"));
  assert.ok(html.includes('src="/static/js/main.js"'));
});

test("the page carries the CSRF token placeholder the server fills in", () => {
  assert.ok(read(join(ROOT, "index.html")).includes('<meta name="csrf-token" content="__CSRF_TOKEN__">'));
});

test("only js/api/ talks to the server: no other file has a server address or calls fetch", () => {
  for (const file of scripts.filter((f) => !name(f).startsWith("js/api/"))) {
    const text = read(file);
    assert.ok(!/["'`]\/api\//.test(text) && !/\bfetch\(/.test(text), name(file));
  }
  assert.ok(!/\bfetch\(/.test(read(join(ROOT, "js/api/endpoints.js"))));
});

test("every module loads: all imports point at files and names that exist", async () => {
  // main.js starts the page as soon as it loads, so it is left out.
  for (const file of scripts.filter((f) => !f.endsWith("main.js"))) {
    await import(pathToFileURL(file).href);
  }
});
