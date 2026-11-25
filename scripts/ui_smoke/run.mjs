// Real-browser UI test. Boots the REAL server, then runs the real UI in a headless Chromium browser
// (Edge or Chrome). It does NOT use DevTools remote debugging (often disabled on managed machines):
// a small proxy sits in front of the server and injects driver.js into the HTML pages; the driver
// clicks through the UI and reports every check back to the proxy.
//
// Usage (from the repo root, virtualenv created, Node.js 22+ installed):
//     node scripts/ui_smoke/run.mjs
// Optional environment variables:
//     BROWSER=path\to\msedge.exe|chrome   (default: Edge on Windows, google-chrome elsewhere)
//     PYTHON=path\to\python               (default: the repo's .venv, else `python`)
import http from "node:http";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(here, "..", "..");
const APP_PORT = 5071, PROXY_PORT = 5072; // avoid 5060/5061: browsers block them ("bad port")
const IS_WIN = process.platform === "win32";
const EDGE = process.env.BROWSER ?? (IS_WIN ? "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" : "google-chrome");
const venvPython = join(REPO, ".venv", IS_WIN ? "Scripts/python.exe" : "bin/python");
const PYTHON = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
const driver = readFileSync(join(here, "driver.js"));
const tmp = mkdtempSync(join(tmpdir(), "agileflow_ui_"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const checks = [], errors = [], misc = [];
let done = false;

// ---------- real server ----------
const server = spawn(PYTHON, ["wsgi.py"], {
  cwd: REPO,
  env: { ...process.env, PORT: String(APP_PORT), SECRET_KEY: "ui-e2e-secret-key-1234567890", WORKER_POLL_SECONDS: "0.2",
         DATABASE_URL: "sqlite:///" + join(tmp, "ui.db").replaceAll("\\", "/") },
  stdio: ["ignore", "pipe", "pipe"],
});
let serverLog = "";
server.stdout.on("data", (d) => (serverLog += d));
server.stderr.on("data", (d) => (serverLog += d));

// ---------- proxy: forwards to the app, injects the driver into HTML, collects reports ----------
const proxy = http.createServer((req, res) => {
  if (req.url === "/__test__/driver.js") { res.writeHead(200, { "Content-Type": "text/javascript" }); return res.end(driver); }
  if (req.url === "/__test__/report" && req.method === "POST") {
    let body = ""; req.on("data", (c) => (body += c));
    req.on("end", () => {
      try {
        const m = JSON.parse(body);
        if (m.type === "check") checks.push(m);
        else if (m.type === "error") errors.push(m.text);
        else if (m.type === "done") done = true;
        else misc.push(m);
      } catch {}
      res.writeHead(204); res.end();
    });
    return;
  }
  const up = http.request({ host: "127.0.0.1", port: APP_PORT, path: req.url, method: req.method,
                            headers: { ...req.headers, host: `127.0.0.1:${APP_PORT}` } }, (ur) => {
    const type = ur.headers["content-type"] ?? "";
    if (!type.includes("text/html")) { res.writeHead(ur.statusCode, ur.headers); return ur.pipe(res); }
    const chunks = []; ur.on("data", (c) => chunks.push(c));
    ur.on("end", () => {
      const html = Buffer.concat(chunks).toString().replace("<head>", '<head><script src="/__test__/driver.js"></script>');
      const headers = { ...ur.headers, "content-length": Buffer.byteLength(html) };
      res.writeHead(ur.statusCode, headers); res.end(html);
    });
  });
  up.on("error", (e) => { res.writeHead(502); res.end(String(e)); });
  req.pipe(up);
});

async function waitHttp(url, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) { try { if ((await fetch(url, { signal: AbortSignal.timeout(2000) })).ok) return true; } catch {} await sleep(250); }
  return false;
}

let edge;
function cleanup() {
  try {
    if (edge?.pid) {
      if (IS_WIN) spawnSync("taskkill", ["/T", "/F", "/PID", String(edge.pid)]); // only the browser we started
      else edge.kill("SIGKILL");
    }
  } catch {}
  try { server.kill(); } catch {}
  try { proxy.close(); } catch {}
}
process.on("exit", cleanup);

console.log("=== Real-browser UI test (Microsoft Edge headless, driver injected via proxy) ===");
await new Promise((r) => proxy.listen(PROXY_PORT, "127.0.0.1", r));
const up = await waitHttp(`http://127.0.0.1:${APP_PORT}/api/health`, 60000);
console.log(up ? "  server ready" : "  SERVER DID NOT START\n" + serverLog.slice(-1500));
if (up) {
  edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--no-sandbox",
    `--user-data-dir=${join(tmp, "profile")}`, `http://127.0.0.1:${PROXY_PORT}/register`], { stdio: "ignore" });
  const end = Date.now() + 150000;
  while (!done && Date.now() < end) await sleep(300);
  await sleep(500);
}
cleanup();

let failed = 0;
for (const c of checks) { console.log(`  ${c.ok ? "PASS" : "FAIL"}  ${c.label}${!c.ok && c.extra ? "  [" + c.extra + "]" : ""}`); if (!c.ok) failed++; }
for (const m of misc) { console.log("  NOTE ", JSON.stringify(m).slice(0, 600)); if (m.type === "fatal" || m.type === "unexpected") failed++; }
const noErrors = errors.length === 0;
console.log(`  ${noErrors ? "PASS" : "FAIL"}  no JavaScript exceptions, console errors or CSP violations in the whole session${noErrors ? "" : "  [" + errors.join(" | ") + "]"}`);
if (!noErrors) failed++;
if (!done) { console.log("  FAIL  driver never reported completion (timed out)"); failed++; }
if (checks.length < 30) { console.log(`  FAIL  only ${checks.length} checks ran (expected 40+)`); failed++; }
const serverErrors = serverLog.split("\n").filter((l) => /Traceback|Exception|ERROR/.test(l));
console.log(`  ${serverErrors.length === 0 ? "PASS" : "FAIL"}  server log has no errors/tracebacks${serverErrors.length ? "  [" + serverErrors.slice(0, 3).join(" | ") + "]" : ""}`);
if (serverErrors.length) failed++;
console.log(failed ? `\nRESULT: ${failed} PROBLEM(S) — ${checks.filter((c) => c.ok).length}/${checks.length} checks passed` : `\nRESULT: ALL UI CHECKS PASSED (${checks.length} checks)`);
process.exit(failed ? 1 : 0);
