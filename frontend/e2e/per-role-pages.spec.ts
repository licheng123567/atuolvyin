// 二轮 e2e：每角色访问 2-3 个关键页，捕捉 nullable / shape 类 runtime bug
import { test, expect, Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

interface PageCheck {
  path: string;
  expectText: RegExp;  // 该页的稳定文案/标题
}

interface RoleCase {
  name: string;
  phone: string;
  pages: PageCheck[];
}

const ROLE_CASES: RoleCase[] = [
  {
    name: "superadmin",
    phone: "13000000000",
    pages: [
      { path: "/super/health", expectText: /系统健康|health/i },
      { path: "/super/audit", expectText: /审计|audit/i },
      { path: "/super/cost", expectText: /成本/ },
      { path: "/super/plans", expectText: /套餐/ },
    ],
  },
  {
    name: "ops",
    phone: "13000000001",
    pages: [
      { path: "/ops/tenants", expectText: /租户/ },
      { path: "/ops/providers", expectText: /服务商/ },
    ],
  },
  {
    name: "admin",
    phone: "13000000002",
    pages: [
      { path: "/admin/dashboard", expectText: /管理看板|dashboard/i },
      { path: "/admin/users", expectText: /用户/ },
      { path: "/admin/scripts", expectText: /话术/ },
      { path: "/admin/legal-conversion", expectText: /法务转化/ },
      { path: "/admin/pool", expectText: /公海/ },
    ],
  },
  {
    name: "supervisor",
    phone: "13000000003",
    pages: [
      { path: "/supervisor/reviews", expectText: /复核|review/i },
      { path: "/supervisor/risk-events", expectText: /风控/ },
      { path: "/supervisor/team-performance", expectText: /团队|绩效/ },
      { path: "/supervisor/live-wall", expectText: /实时|通话墙/ },
    ],
  },
  {
    name: "agent (internal)",
    phone: "13000000004",
    pages: [
      { path: "/agent/cases", expectText: /案件/ },
    ],
  },
  {
    name: "legal",
    phone: "13000000006",
    pages: [
      { path: "/legal/cases", expectText: /法务|案件/ },
    ],
  },
  {
    name: "coordinator",
    phone: "13000000007",
    pages: [
      { path: "/workorder/orders", expectText: /工单/ },
    ],
  },
  {
    name: "project_manager (tenant)",
    phone: "13000000008",
    pages: [
      { path: "/pm/dashboard", expectText: /项目|看板/ },
    ],
  },
  {
    name: "project_manager (provider)",
    phone: "13000000009",
    pages: [
      { path: "/pm/dashboard", expectText: /项目|看板/ },
    ],
  },
  {
    name: "admin (provider)",
    phone: "13000000010",
    pages: [
      { path: "/provider/dashboard", expectText: /服务商|看板/ },
      { path: "/provider/team", expectText: /团队/ },
    ],
  },
  // 13000000011: provider-side external agent — shares the /agent/cases route with property agents
  {
    name: "agent (provider external)",
    phone: "13000000011",
    pages: [
      { path: "/agent/cases", expectText: /案件/ },
    ],
  },
  // 13000000012: provider-side supervisor — Phase 1 起 /supervisor/* 端点已 scope-aware，
  // 服务商督导可正常访问本服务商数据（公海 / 质检 / 团队监控等）。
  {
    name: "supervisor (provider)",
    phone: "13000000012",
    pages: [
      { path: "/supervisor/cases", expectText: /案件|公海/ },
      { path: "/supervisor/reviews", expectText: /复核|review/i },
      { path: "/supervisor/team-performance", expectText: /团队|绩效/ },
    ],
  },
  {
    name: "legal (provider)",
    phone: "13000000013",
    pages: [
      { path: "/provider/legal/cases", expectText: /法务案件|案件/ },
      { path: "/provider/legal/requests", expectText: /转化请求|请求/ },
    ],
  },
];

async function dismissAppIntroIfPresent(page: Page) {
  const closeBtn = page.getByRole("button", { name: "知道了" });
  try {
    await closeBtn.waitFor({ state: "visible", timeout: 2500 });
    await closeBtn.click();
    await closeBtn.waitFor({ state: "hidden", timeout: 2000 });
  } catch {
    // 不存在
  }
}

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAppIntroIfPresent(page);
}

for (const rc of ROLE_CASES) {
  test.describe(`${rc.name} 关键页面冒烟`, () => {
    for (const pg of rc.pages) {
      test(`${rc.name} → ${pg.path} 应渲染`, async ({ page }) => {
        const errors: string[] = [];
        page.on("pageerror", (err) => errors.push(`PAGE EXCEPTION: ${err.message}`));
        page.on("response", (r) => {
          if (r.status() >= 500) errors.push(`HTTP ${r.status()} ${r.url()}`);
        });

        await login(page, rc.phone);
        await page.goto(pg.path);
        await dismissAppIntroIfPresent(page);

        // 不应被踢回 /login（dataProvider 401 redirect）
        await page.waitForLoadState("networkidle");
        expect(page.url(), `pages should not redirect to /login: ${pg.path}`).not.toContain("/login");

        // 该页的稳定文案应可见
        await expect(page.getByText(pg.expectText).first()).toBeVisible({ timeout: 5_000 });

        // 不应有未捕获异常或 5xx
        expect(errors, `${pg.path} 渲染时无 runtime error`).toEqual([]);
      });
    }
  });
}
