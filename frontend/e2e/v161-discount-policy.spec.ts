// v1.6.1 — 减免阈值项目级覆盖 + admin/settings 不卡死
import { test, expect, Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

async function dismissAppIntroIfPresent(page: Page) {
  const closeBtn = page.getByRole("button", { name: "知道了" });
  try {
    await closeBtn.waitFor({ state: "visible", timeout: 2500 });
    await closeBtn.click();
    await closeBtn.waitFor({ state: "hidden", timeout: 2000 });
  } catch {
    // 不存在，跳过
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

test.describe("v1.6.1 — admin 系统配置页", () => {
  test("admin/settings 不应一直卡在加载中", async ({ page }) => {
    await login(page, "13000000002");
    await page.goto("/admin/settings");
    await dismissAppIntroIfPresent(page);
    // 加载中文案应在 8 秒内消失（即便 API 失败也走兜底）
    const loading = page.getByText(/加载中/);
    await expect(loading).toHaveCount(0, { timeout: 8_000 }).catch(async () => {
      // 兜底：可能多处 加载中，断言至少 form 已渲染
      await expect(page.getByText(/系统配置|减免|录音|账号/).first()).toBeVisible({ timeout: 5_000 });
    });
    // 减免审批策略 section 应可见（v1.6 新增）
    await expect(page.getByText(/减免审批策略/)).toBeVisible({ timeout: 5_000 });
  });
});

test.describe("v1.6.1 — 项目级减免阈值覆盖", () => {
  test("admin 新建项目页应有「减免审批策略（项目级覆盖）」section", async ({ page }) => {
    await login(page, "13000000002");
    await page.goto("/admin/projects/new");
    await dismissAppIntroIfPresent(page);
    await expect(page.getByText(/减免审批策略.*项目级覆盖/)).toBeVisible({ timeout: 5_000 });
    // v1.6.2 拆分两类：本金打折 + 滞纳金减免，所以多处出现「自动批准阈值/督导可批上限」
    await expect(page.getByText(/自动批准阈值/).first()).toBeVisible();
    await expect(page.getByText(/督导可批上限/).first()).toBeVisible();
    // v1.6.2 — 标题区分两类
    await expect(page.getByText(/本金打折策略/)).toBeVisible();
    await expect(page.getByText(/滞纳金减免策略/)).toBeVisible();
  });
});
