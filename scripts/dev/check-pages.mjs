// Opens every dashboard page in a headless browser and fails on a script error, a file that didn't load, an error
// message on the page, or a page that drew nothing. Talks to the browser over the DevTools protocol (Node 22's
// built-in WebSocket; no packages). The page list comes from dashboard/js/main.js, so new pages are checked too.
// Run by check_pages.py, which starts a throwaway Home Base with demo data first. Given a folder, it also saves the
// top of each page there as <page>.png, for the user guide.
//
//   node scripts/dev/check-pages.mjs <browser program> <Home Base address> <empty profile folder> [screenshot folder]

import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [browserPath, base, profile, shots] = process.argv.slice(2);
const MAIN = new URL("../../dashboard/js/main.js", import.meta.url);
const PAGES = [...readFileSync(MAIN, "utf8").matchAll(/\{ id: "([\w-]+)", label: "[^"]+", load:/g)].map((m) => m[1]);
const PORT = 9333;
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

if (PAGES.length < 10) throw new Error(`Found only ${PAGES.length} pages in main.js; has its format changed?`);

const browser = spawn(browserPath, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--disable-extensions", "about:blank"], { stdio: "ignore" });

async function findPage() {
  for (let tries = 0; tries < 50; tries++) {
    await sleep(200);
    try {
      const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = targets.find((t) => t.type === "page");
      if (page) return page;
    } catch { /* the browser isn't listening yet */ }
  }
  throw new Error("The browser didn't start.");
}

const ws = new WebSocket((await findPage()).webSocketDebuggerUrl);
await new Promise((open) => ws.addEventListener("open", open, { once: true }));

let lastId = 0;
const replies = new Map();
const problems = [];
let current = "(loading)";
ws.addEventListener("message", ({ data }) => {
  const { id, result, method, params } = JSON.parse(data);
  if (id && replies.has(id)) { replies.get(id)(result); replies.delete(id); }
  if (method === "Runtime.exceptionThrown") {
    const d = params.exceptionDetails;
    problems.push(`${current}: script error: ${d.exception?.description ?? d.text}`);
  } else if (method === "Log.entryAdded" && params.entry.level === "error") {
    problems.push(`${current}: ${params.entry.text} ${params.entry.url ?? ""}`.trim());
  } else if (method === "Runtime.consoleAPICalled" && params.type === "error") {
    problems.push(`${current}: console.error: ${params.args.map((a) => a.value ?? a.description).join(" ")}`);
  }
});
const send = (method, params = {}) => new Promise((reply) => {
  replies.set(++lastId, reply);
  ws.send(JSON.stringify({ id: lastId, method, params }));
});
const evaluate = async (expression) =>
  (await send("Runtime.evaluate", { expression, returnByValue: true })).result.value;

try {
  for (const domain of ["Runtime", "Log", "Page"]) await send(`${domain}.enable`);
  if (shots) {
    await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
  }
  await send("Page.navigate", { url: `${base}/#${PAGES[0]}` });
  await sleep(3000);
  for (const page of PAGES) {
    current = page;
    await evaluate(`location.hash = ${JSON.stringify(page)}`);
    await sleep(1500);
    const shown = await evaluate(`({
      characters: document.getElementById("view").innerText.trim().length,
      errors: [...document.querySelectorAll("#view [role=alert]")].map((e) => e.innerText.trim()).filter(Boolean),
    })`);
    if (shown.characters < 20) problems.push(`${page}: the page drew almost nothing (${shown.characters} characters)`);
    for (const error of shown.errors) problems.push(`${page}: error shown on the page: ${error}`);
    if (shots) {
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      writeFileSync(join(shots, `${page}.png`), Buffer.from(data, "base64"));
    }
    console.log(`${page.padEnd(16)} ${shown.errors.length || shown.characters < 20 ? "PROBLEM" : "ok"}`);
  }
} finally {
  ws.close();
  browser.kill();
}
console.log(problems.length ? `\n${problems.join("\n")}` : `\nAll ${PAGES.length} pages opened without problems.`);
process.exit(problems.length ? 1 : 0);
