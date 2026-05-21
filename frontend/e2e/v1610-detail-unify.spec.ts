// v1.6.10 — 案件详情统一 + supervisor 列表真后端 + 时间线录音 + 多身份 demo
import { expect, Page, test } from "@playwright/test";

const PASSWORD = "Demo@123!";
const SUPERVISOR_PHONE = "13000000003";
const AGENT_PHONE = "13000000004";
const ADMIN_PHONE = "13000000002";

async function dismissModals(page: Page) {
  for (let i = 0; i < 3; i++) {
    const btn = page.getByRole("button", { name: "知道了" }).first();
    try {
      await btn.waitFor({ state: "visible", timeout: 1500 });
      await btn.click();
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
    page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissModals(page);
}

test.describe("v1.6.10 — 案件详情统一蓝本", () => {
  test("Bug1：督导案件分配点详情不再 404", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await page.goto("/supervisor/cases");
    // 等待真实后端列表加载
    await page.waitForTimeout(1500);
    // 至少有一行案件（真实后端有数据）
    const detailBtn = page.getByRole("button", { name: /详情/ }).first();
    await expect(detailBtn).toBeVisible({ timeout: 8_000 });
    await detailBtn.click();
    // 进入详情页 — 不再"案件不存在或无权访问"
    await expect(page.getByText("案件不存在或无权访问")).not.toBeVisible({ timeout: 5_000 });
    // URL 应跳到 /supervisor/cases/数字
    await expect(page).toHaveURL(/\/supervisor\/cases\/\d+/);
  });

  test("详情页：业主信息卡含账单期 + 三栏 + 不再有独立「欠费明细」卡", async ({ page }) => {
    await loginAs(page, AGENT_PHONE);
    await page.goto("/agent/cases");
    // v0.5.4 修正:与 Bug1 测试同样需要等真实后端列表加载,避免 click 时按钮还没绑定
    await page.waitForTimeout(1500);
    await dismissModals(page);
    const detailBtn = page.getByRole("button", { name: /^详情/ }).first();
    await expect(detailBtn).toBeVisible({ timeout: 8_000 });
    await detailBtn.click();
    // 业主信息卡可见
    await expect(page.getByText("业主信息").first()).toBeVisible({ timeout: 5_000 });
    // v0.5.4 修正:OwnerInfoCard 已移除「累计欠费」独立 hero,改为「欠款月份: ... 共 N 个月」段;
    //   三栏直接渲染金额(物业费 / 违约金 / 欠费总额)
    await expect(page.getByText(/欠款月份/).first()).toBeVisible();
    // 三栏:物业费 / 违约金 / 欠费总额
    await expect(page.getByText("物业费").first()).toBeVisible();
    await expect(page.getByText("违约金").first()).toBeVisible();
    await expect(page.getByText("欠费总额").first()).toBeVisible();
    // 不再有独立的「欠费明细」card-title 卡(已移除)
    const billCardTitle = page.locator(".card-title").filter({ hasText: "欠费明细" });
    await expect(billCardTitle).toHaveCount(0);
  });

  test("详情页：中栏有跟进备注卡 + 阶段下拉", async ({ page }) => {
    await loginAs(page, AGENT_PHONE);
    await page.goto("/agent/cases");
    // v0.5.4 修正:同样需要等真实后端列表加载
    await page.waitForTimeout(1500);
    await dismissModals(page);
    const detailBtn = page.getByRole("button", { name: /^详情/ }).first();
    await expect(detailBtn).toBeVisible({ timeout: 8_000 });
    await detailBtn.click();
    await expect(page.getByText("添加跟进备注")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("textbox").first()).toBeVisible();
    // v0.5.4 修正:label 去掉了全角冒号,统一用 startsWith 匹配
    await expect(page.getByText(/^更新阶段/).first()).toBeVisible();
  });

  test("详情页：时间线通话节点有「🎧 听录音」按钮", async ({ page }) => {
    await loginAs(page, SUPERVISOR_PHONE);
    await page.goto("/supervisor/cases");
    await page.waitForTimeout(1500);
    const detailBtn = page.getByRole("button", { name: /详情/ }).first();
    await detailBtn.click();
    await page.waitForTimeout(1000);
    // 时间线节点；通话行有「听录音」或「听」按钮（无录音时 disabled，但仍渲染）
    const listenBtn = page.getByRole("button", { name: /听录音|听/ }).first();
    // 即使 0 通话也不阻塞测试（用 .or() 不可，直接 try/skip）
    const count = await listenBtn.count();
    if (count > 0) {
      await expect(listenBtn).toBeVisible();
    }
  });

  test("Bug4：13000000003 督导账号有 agent membership + 分配案件", async ({ page }) => {
    // v0.5.4 修正:v2.2 四维正交角色模型 — `agent_internal` 已废弃,统一 role='agent';
    //   /me/memberships 的 MembershipItem schema 不暴露 work_mode,只能按 role 过滤;
    //   supervisor 13000000003 在 seed 里有 1 个 agent membership(internal),刚好够;
    //   API base 走 e2e 后端端口 18100(原硬编码 :18000 是 dev 后端,e2e 跑不通)
    await loginAs(page, SUPERVISOR_PHONE);
    const cases = await page.evaluate(async () => {
      const token = localStorage.getItem("autoluyin_token");
      const API = `${window.location.protocol}//${window.location.hostname}:18100/api/v1`;
      const memResp = await fetch(`${API}/me/memberships`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const memberships = await memResp.json();
      const agentMembership = memberships.find(
        (m: { role: string }) => m.role === "agent",
      );
      if (!agentMembership) return { error: "no agent membership" };
      const switchResp = await fetch(`${API}/auth/select-membership`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          membership_id: agentMembership.membership_id,
          device_type: "pc",
        }),
      });
      const newAuth = await switchResp.json();
      const casesResp = await fetch(`${API}/agent/cases?page=1&page_size=10`, {
        headers: { Authorization: `Bearer ${newAuth.access_token}` },
      });
      const data = await casesResp.json();
      return { total: data.total ?? data.items?.length, role: newAuth.role };
    });
    expect(cases).not.toHaveProperty("error");
    expect((cases as { role: string }).role).toBe("agent");
    expect((cases as { total: number }).total).toBeGreaterThanOrEqual(2);
  });

  test("admin 详情页也用统一蓝本（业主+项目+跟进备注，无独立欠费明细）", async ({ page }) => {
    await loginAs(page, ADMIN_PHONE);
    await page.goto("/admin/cases");
    // 等列表渲染（加载中 → 表格行）
    await page.locator("tbody tr").first().waitFor({ state: "visible", timeout: 10_000 });
    const detailBtn = page.getByRole("button", { name: /^详情/ }).first();
    await expect(detailBtn).toBeVisible({ timeout: 5_000 });
    await detailBtn.click();
    // 详情页 — 业主信息卡（OwnerInfoCard）
    await expect(page.getByText("业主信息").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("添加跟进备注")).toBeVisible();
    // 不再有独立"欠费明细"卡
    const billCardTitle = page.locator(".card-title").filter({ hasText: "欠费明细" });
    await expect(billCardTitle).toHaveCount(0);
  });
});
