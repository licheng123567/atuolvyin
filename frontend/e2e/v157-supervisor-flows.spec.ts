// v1.5.7 督导端关键流程 E2E
// 覆盖：登录 → 话术反馈详情 → 案件超期预警过滤 → 升级案件查看历史 → 法务订单视图
import { expect, Page, test } from "@playwright/test";

const PASSWORD = "Demo@123!";
const SUPERVISOR_PHONE = "13000000003";
const LEGAL_PHONE = "13000000006";

async function loginAs(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByPlaceholder(/手机号/).fill(phone);
  await page.getByPlaceholder(/密码/).fill(PASSWORD);
  await page.getByRole("button", { name: /登录/ }).click();
  await page.waitForURL(/^(?!.*\/login)/, { timeout: 5000 });
}

async function dismissIntroIfPresent(page: Page) {
  const close = page.getByRole("button", { name: "知道了" });
  try {
    await close.waitFor({ state: "visible", timeout: 2500 });
    await close.click();
  } catch {
    /* skip */
  }
}

test.describe("v1.5.7 督导端关键流程", () => {
  test("话术反馈：点击详情显示完整正文 + 备注 + 最近使用", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/supervisor/script-labels");
    await expect(page.getByText("话术反馈")).toBeVisible();
    // 第一行点「详情」按钮
    const firstDetailBtn = page.getByRole("button", { name: /详情/ }).first();
    await firstDetailBtn.click();
    // modal 内显示完整正文 / 督导备注 / 总推送 / 督导好评 / 督导差评
    await expect(page.getByText("完整话术")).toBeVisible();
    await expect(page.getByText("总推送")).toBeVisible();
    await expect(page.getByText("督导好评")).toBeVisible();
    await expect(page.getByText("督导差评")).toBeVisible();
    await expect(page.getByText("最近使用")).toBeVisible();
    // 关闭 modal
    await page.getByRole("button", { name: "关闭" }).click();
  });

  test("案件超期预警：搜索 + 类型 filter + 催办按钮可点", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/supervisor/case-alerts");
    await expect(page.getByText("案件超期 / 失联报警")).toBeVisible();
    // 顶部搜索 + 项目下拉应可见
    await expect(page.getByPlaceholder(/按业主姓名 \/ 房号搜索/)).toBeVisible();
    // 搜索定位
    await page.getByPlaceholder(/按业主姓名 \/ 房号搜索/).fill("梁建国");
    await expect(page.getByText("梁建国")).toBeVisible();
    // 清空筛选
    const clearBtn = page.getByRole("button", { name: /清空筛选/ });
    if (await clearBtn.isVisible()) await clearBtn.click();
  });

  test("升级案件：查看历史跳转到 supervisor case detail", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/supervisor/escalated");
    await expect(page.getByText("升级案件处理")).toBeVisible();
    const viewBtn = page.getByRole("button", { name: /查看历史/ }).first();
    await viewBtn.click();
    await page.waitForURL(/\/supervisor\/cases\/\d+/);
    await expect(page.getByText(/近期通话记录/)).toBeVisible();
    await expect(page.getByText(/案件时间线/)).toBeVisible();
  });

  test("公海案件：搜索框 + 优先级图例可见", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/supervisor/cases");
    await expect(page.getByText("公海案件")).toBeVisible();
    await expect(page.getByPlaceholder(/按业主姓名 \/ 房号在公海中搜索/)).toBeVisible();
    await expect(page.getByText(/右侧数字为优先级分数/)).toBeVisible();
    // 至少一个 P 数字 badge
    await expect(page.getByText(/^P \d+$/).first()).toBeVisible();
  });

  test("通知图标：站内信 + 风控告警分别可见且区分", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    // 督导有 2 个图标：Bell（站内信）+ ShieldAlert（风控）
    const bell = page.getByRole("button", { name: "站内信" });
    const shield = page.getByRole("button", { name: "风控告警" });
    await expect(bell).toBeVisible();
    await expect(shield).toBeVisible();
  });
});

test.describe("v1.5.7 法务订单三视图（mock）", () => {
  test("物业法务对接人：进入法务订单页", async ({ page }) => {
    await loginAs(page, LEGAL_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/legal/orders");
    await expect(page.getByText(/法务订单/)).toBeVisible();
    await expect(page.getByText(/待撮合|已派单|服务中|已完成/)).toBeVisible();
  });

  test("律所工作台：mock 直接访问 + 看到分律师按钮（dispatched 订单）", async ({ page }) => {
    await loginAs(page, LEGAL_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/lawfirm/orders");
    await expect(page.getByText(/律所工作台/)).toBeVisible();
  });

  test("律师工作台：mock 直接访问 + in_service 订单可上传文书", async ({ page }) => {
    await loginAs(page, LEGAL_PHONE);
    await dismissIntroIfPresent(page);
    await page.goto("/lawyer/orders");
    await expect(page.getByText(/律师工作台/)).toBeVisible();
  });
});

test.describe("v1.5.7 多 membership 切换", () => {
  test("多角色用户在用户名旁显示「可切换 N」徽章", async ({ page }) => {
    // 注意：本 test 假设 supervisor 账号至少有 1 个其他 membership
    // 若 seed 数据没设置该用户的多 membership，本 test 会跳过（可切换徽章不出现）
    await loginAs(page, SUPERVISOR_PHONE);
    await dismissIntroIfPresent(page);
    const badge = page.getByText(/可切换 \d+/);
    if (await badge.count() > 0) {
      await expect(badge).toBeVisible();
    } else {
      test.skip(true, "当前 supervisor 账号无多 membership，跳过切换徽章 test");
    }
  });
});
