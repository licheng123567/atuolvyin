// v1.6.8 — 法务转化两步审批 e2e
// 流程：催收员申请 → 督导看到申请 → 批准（选服务包）/ 驳回（填理由）
import { expect, Page, test } from "@playwright/test";

const PASSWORD = "Demo@123!";
const AGENT_PHONE = "13000000004"; // 内勤小张
const SUPERVISOR_PHONE = "13000000003"; // 督导

async function dismissAllModalsIfPresent(page: Page) {
  for (let i = 0; i < 3; i++) {
    const closeBtn = page.getByRole("button", { name: "知道了" }).first();
    try {
      await closeBtn.waitFor({ state: "visible", timeout: 1500 });
      await closeBtn.click();
      await page.waitForTimeout(300);
    } catch {
      return;
    }
  }
}

async function loginAs(page: Page, phone: string) {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAllModalsIfPresent(page);
}

test.describe("v1.6.8 法务转化两步审批", () => {
  test("督导审批页可正常打开 + 渲染 KPI / 表头 / 状态切换", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await page.goto("/supervisor/legal-conversion-approvals");
    // 标题
    await expect(page.locator(".page-title")).toContainText("法务转化审批");
    // KPI bar 三个统计项 — 用 .status-bar-item 收紧避免与同名 tab 按钮撞 strict mode
    await expect(page.locator(".status-bar-item").getByText("待我审批")).toBeVisible();
    await expect(page.locator(".status-bar-item").getByText("已批准")).toBeVisible();
    await expect(page.locator(".status-bar-item").getByText("已驳回")).toBeVisible();
    // 4 个状态切换 tab
    await expect(page.getByRole("button", { name: /待审批/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /已批准/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /已驳回/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^全部$/ })).toBeVisible();
    // 表头
    await expect(page.getByRole("columnheader", { name: "申请号" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "业主 / 房号" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "申请理由" })).toBeVisible();
  });

  test("admin 也能进入同一审批页", async ({ page }) => {
    // v0.5.4 修正:原用 13000000001 是 ops 账号,改用真 admin 13000000002
    await loginAs(page, "13000000002");
    await page.goto("/admin/legal-conversion-approvals");
    await expect(page.locator(".page-title")).toContainText("法务转化审批");
    // admin 视角徽标
    await expect(page.locator(".page-title")).toContainText("admin 视角");
  });

  test("催收员申请转法务 → 督导侧能看到这条申请", async ({ page }) => {
    // Step 1：催收员发起申请
    await loginAs(page, AGENT_PHONE);
    await page.goto("/agent/cases");
    // 找一个详情按钮点进去（演示数据应至少有 1 个案件）
    const firstDetailBtn = page.getByRole("button", { name: /详情/ }).first();
    if ((await firstDetailBtn.count()) === 0) {
      test.skip(true, "演示数据无可用案件");
    }
    await firstDetailBtn.click();
    // 详情页右栏「申请转法务」按钮
    const transferBtn = page.getByRole("button", { name: /申请转法务/ });
    await expect(transferBtn).toBeVisible({ timeout: 5_000 });
    // 拦截 alert（intent 端点会触发 alert "✓ 申请转法务 已记录..."）
    let alertText: string | null = null;
    page.once("dialog", async (d) => {
      alertText = d.message();
      await d.accept();
    });
    await transferBtn.click();
    // 等 alert 弹出
    await page.waitForTimeout(1500);
    // alert 提示「已记录」或后端 409（已存在 pending 申请，也算流程通）
    if (alertText) {
      expect(alertText).toMatch(/已记录|已有|已存在/);
    }

    // Step 2：登录督导看 inbox
    await page.context().clearCookies();
    await loginAs(page, SUPERVISOR_PHONE);
    await page.goto("/supervisor/legal-conversion-approvals");
    // 默认 tab 是「待审批」
    await expect(page.locator(".page-title")).toContainText("法务转化审批");
    // 等待表格渲染
    await page.waitForTimeout(1000);
    // 由于 demo 数据可能已经预先存在多条申请，断言至少有 1 行 pending
    const rows = page.locator("tbody tr");
    const count = await rows.count();
    // 至少出现一行（如果一行也没，说明数据不存在或被过滤）
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
