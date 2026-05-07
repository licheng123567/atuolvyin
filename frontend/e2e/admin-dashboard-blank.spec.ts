import { expect, test } from "@playwright/test";

test("admin 13000000002 sees dashboard data", async ({ page }) => {
  const consoleMsgs: string[] = [];
  const failedReqs: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      consoleMsgs.push(`[${msg.type()}] ${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => {
    consoleMsgs.push(`[pageerror] ${err.message}`);
  });
  page.on("requestfailed", (req) => {
    failedReqs.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
  });
  page.on("response", async (resp) => {
    if (!resp.ok() && resp.url().includes("/api/")) {
      let body = "";
      try {
        body = await resp.text();
      } catch {
        // ignore
      }
      consoleMsgs.push(
        `[http ${resp.status()}] ${resp.url()} body=${body.slice(0, 200)}`,
      );
    }
  });

  await page.goto("/login");
  await page.fill('input[id="phone"]', "13000000002");
  await page.fill('input[id="password"]', "Demo@123!");
  await page.click('button[type="submit"]');

  // wait for redirect to dashboard
  await page.waitForURL(/\/admin\/dashboard/, { timeout: 10000 });

  // wait for at least 2s to let dashboard render
  await page.waitForTimeout(3000);

  // capture screenshot for debugging
  await page.screenshot({
    path: "playwright-report/admin-dashboard-after-login.png",
    fullPage: true,
  });

  const bodyText = await page.locator("body").innerText();

  console.log("=== console errors ===");
  for (const m of consoleMsgs) console.log(m);
  console.log("=== failed requests ===");
  for (const r of failedReqs) console.log(r);
  console.log("=== body text snippet ===");
  console.log(bodyText.slice(0, 1500));

  // close the App download modal if it appears (covers the page)
  const dontShowAgain = page.getByText("不再提示").first();
  if (await dontShowAgain.isVisible({ timeout: 2000 }).catch(() => false)) {
    await dontShowAgain.click();
    await page.getByRole("button", { name: "知道了" }).click();
    await page.waitForTimeout(500);
  }

  // assert main KPI label visible
  await expect(page.getByText("今日外呼").first()).toBeVisible({
    timeout: 5000,
  });

  // assert project KPI section visible (v1.4 — by-project)
  await expect(page.getByText("按项目分维度").first()).toBeVisible({
    timeout: 5000,
  });
  await expect(page.getByText("金桂园 2026 年欠费催收").first()).toBeVisible();
  await expect(page.getByText("翠湖湾电梯专项整改").first()).toBeVisible();
});
