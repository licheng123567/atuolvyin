// v2.4 — Diagnose PC /login red errors after restoring v2.3 Module 4 changes.
// Captures: console errors/warnings, page network failures, and a screenshot.
import { test, expect } from "@playwright/test";

test("PC /login should render without console errors", async ({ page }) => {
  const consoleMsgs: { type: string; text: string; location?: string }[] = [];
  const pageErrors: string[] = [];
  const failedRequests: { url: string; failure: string }[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      const loc = msg.location();
      consoleMsgs.push({
        type: msg.type(),
        text: msg.text(),
        location: loc ? `${loc.url}:${loc.lineNumber}` : undefined,
      });
    }
  });
  page.on("pageerror", (err) => {
    pageErrors.push(`${err.name}: ${err.message}\n${err.stack ?? ""}`);
  });
  page.on("requestfailed", (req) => {
    failedRequests.push({
      url: req.url(),
      failure: req.failure()?.errorText ?? "unknown",
    });
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      failedRequests.push({
        url: res.url(),
        failure: `HTTP ${res.status()}`,
      });
    }
  });

  await page.goto("/login", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  await page.screenshot({
    path: "test-results/v240-pc-login.png",
    fullPage: true,
  });

  console.log("\n=== CONSOLE (error/warning) ===");
  for (const m of consoleMsgs) {
    console.log(`[${m.type}] ${m.text}` + (m.location ? `  @ ${m.location}` : ""));
  }
  console.log("\n=== PAGE ERRORS (uncaught) ===");
  for (const e of pageErrors) console.log(e);
  console.log("\n=== NETWORK FAILURES (>=400 / failed) ===");
  for (const r of failedRequests) console.log(`${r.failure}  ${r.url}`);

  // 软断言：先收集再判定
  const hardErrors = pageErrors.length;
  const consoleErrorCount = consoleMsgs.filter((m) => m.type === "error").length;
  console.log(
    `\n=== SUMMARY: pageErrors=${hardErrors}  consoleErrors=${consoleErrorCount}  netFails=${failedRequests.length} ===`,
  );

  // 红色基本是 React 渲染抛错或 4xx/5xx；任一非空都视为失败
  expect(pageErrors, "uncaught page errors").toEqual([]);
  expect(consoleErrorCount, "console errors").toBe(0);
});
