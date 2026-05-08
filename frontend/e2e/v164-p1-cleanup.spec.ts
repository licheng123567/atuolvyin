// v1.6.4 — P1 清理 + 团队报表 + 升级案件分页
import { test, expect, Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

async function dismissAppIntroIfPresent(page: Page) {
  const closeBtn = page.getByRole("button", { name: "知道了" });
  try {
    await closeBtn.waitFor({ state: "visible", timeout: 2500 });
    await closeBtn.click();
    await closeBtn.waitFor({ state: "hidden", timeout: 2000 });
  } catch {
    // not present
  }
}

async function login(page: Page, phone: string, password = PASSWORD) {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', password);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAppIntroIfPresent(page);
}

test.describe("v1.6.4 — P1 清理", () => {
  test("admin 侧边栏不应再有 P1 字样", async ({ page }) => {
    await login(page, "13000000002");
    // 侧边栏内不应包含 P1 badge
    const sidebar = page.locator("nav, aside, [class*=sidebar i]").first();
    await expect(sidebar.getByText(/^P1$/)).toHaveCount(0);
  });

  test("supervisor 侧边栏不应再有 P1 字样", async ({ page }) => {
    await login(page, "13000000003");
    const sidebar = page.locator("nav, aside, [class*=sidebar i]").first();
    await expect(sidebar.getByText(/^P1$/)).toHaveCount(0);
  });
});

test.describe("v1.6.4 — 督导团队报表", () => {
  test("supervisor/stats 应渲染漏斗 + 趋势 + 排名（替换原 P1 banner）", async ({ page }) => {
    await login(page, "13000000003");
    await page.goto("/supervisor/stats");
    await dismissAppIntroIfPresent(page);
    // 关键标题应可见
    await expect(page.getByText("回款转化漏斗")).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText("通话量趋势")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("团队成员排名")).toBeVisible({ timeout: 5_000 });
    // 不应再显示 P1 占位 banner 文字
    await expect(page.getByText(/v1\.6 上线/)).toHaveCount(0);
  });
});

test.describe("v1.6.4 — 督导升级案件分页", () => {
  test("supervisor/escalated 应渲染列表（mock fallback 或真后端均可）", async ({ page }) => {
    await login(page, "13000000003");
    await page.goto("/supervisor/escalated");
    await dismissAppIntroIfPresent(page);
    // 「升级案件处理」是 page-title div，不是 heading；用 text 匹配
    await expect(page.getByText("升级案件处理").first()).toBeVisible({ timeout: 8_000 });
    // 「介入处理」按钮（每行一个）应至少出现一次（demo 数据有 escalated 案件）
    await expect(page.getByRole("button", { name: "介入处理" }).first()).toBeVisible({ timeout: 8_000 });
  });
});
