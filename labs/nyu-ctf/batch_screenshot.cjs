// batch_screenshot.cjs — one persistent chromium for N GET-replay shots.
//
// Usage: node batch_screenshot.cjs <playwright_pkg_dir> <jobs.json> <results.jsonl>
//   jobs.json: [{"name":"01-seq12","url":"http://.../?a=1&b=2","out":"01-seq12.png",
//                "timeout_ms":25000}, ...]
//
// Why this exists (batch 9, 6C root cause): the previous per-page path spawned
// `npx.cmd playwright screenshot <url> <out>` per shot. Two independent failure
// modes came with that: (1) npx.cmd routes argv through cmd.exe, which mangles
// URL query strings containing & % ^ (split/expansion — the "查询串失败");
// (2) every shot cold-launched a browser, so back-to-back shots raced on the
// browser/profile (the "连发间歇失败"). Here URLs travel inside a JSON file,
// args are plain filesystem paths, and one browser serves all pages.
const fs = require("fs");
const path = require("path");

const [pkgDir, jobsPath, resultsPath] = process.argv.slice(2);
if (!pkgDir || !jobsPath || !resultsPath) {
  console.error("usage: node batch_screenshot.cjs <pkg_dir> <jobs.json> <results.jsonl>");
  process.exit(2);
}

const { chromium } = require(path.resolve(pkgDir));
const jobs = JSON.parse(fs.readFileSync(jobsPath, "utf8"));

function record(row) {
  fs.appendFileSync(resultsPath, JSON.stringify(row) + "\n");
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch (exc) {
    record({ name: null, ok: false, detail: `launch: ${String(exc).slice(0, 300)}` });
    process.exit(0);
  }
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  for (const job of jobs) {
    const page = await context.newPage();
    try {
      await page.goto(job.url, {
        timeout: Number(job.timeout_ms) || 25000,
        waitUntil: "domcontentloaded",
      });
      await page.waitForTimeout(1200);
      await page.screenshot({ path: job.out, fullPage: false });
      record({ name: job.name, ok: true, detail: "ok" });
    } catch (exc) {
      record({
        name: job.name,
        ok: false,
        detail: String(exc).slice(0, 300),
      });
    } finally {
      await page.close().catch(() => {});
    }
  }
  await browser.close();
  process.exit(0);
})();
