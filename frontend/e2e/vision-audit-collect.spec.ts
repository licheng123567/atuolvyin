// v0.5.6 — AI 视觉巡检 PoC:第一阶段「截图收集」
//
// 目的:遍历 14 角色 × 各自能访问的关键页面,把全屏截图 + console/网络错误存到本地,
// 再由 scripts/vision-audit-analyze.mjs 把每张图喂给 Claude Vision 出 UX 审计报告。
// 详见 docs/QA_PLAYBOOKS/vision-audit.md。
//
// 跑法:`npx playwright test e2e/vision-audit-collect.spec.ts --project=chromium`
// 输出:vision-audit-output/{role}/{slug}.png + .json(每页元数据)
//
// 不进 CI(成本/速度先评估);手动跑出报告的流程,见上文 playbook。

import { test, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUTPUT_DIR = path.resolve(__dirname, "../vision-audit-output");

const PASSWORD = "Demo@123!";

interface PageSpec {
  path: string;
  slug: string; // 用于文件名,如 "admin-dashboard"
}

interface RoleSpec {
  name: string;
  phone: string;
  pages: PageSpec[];
}

// 复用 per-role-pages.spec.ts 的角色 + 路径列表(同步保持一致);本期覆盖关键页,
// 后续可扩展。
const ROLE_SPECS: RoleSpec[] = [
  {
    name: "superadmin", phone: "13000000000",
    pages: [
      { path: "/super/health", slug: "super-health" },
      { path: "/super/audit", slug: "super-audit" },
      { path: "/super/cost", slug: "super-cost" },
      { path: "/super/plans", slug: "super-plans" },
    ],
  },
  {
    name: "ops", phone: "13000000001",
    pages: [
      { path: "/ops/tenants", slug: "ops-tenants" },
      { path: "/ops/providers", slug: "ops-providers" },
      { path: "/ops/settlements", slug: "ops-settlements" },
      { path: "/ops/law-firms", slug: "ops-law-firms" },
      { path: "/ops/legal-packages", slug: "ops-legal-packages" },
    ],
  },
  {
    name: "admin", phone: "13000000002",
    pages: [
      { path: "/admin/dashboard", slug: "admin-dashboard" },
      { path: "/admin/users", slug: "admin-users" },
      { path: "/admin/cases", slug: "admin-cases" },
      { path: "/admin/pool", slug: "admin-pool" },
      { path: "/admin/scripts", slug: "admin-scripts" },
      { path: "/admin/legal-conversion", slug: "admin-legal-conversion" },
      { path: "/admin/discount-approvals", slug: "admin-discount-approvals" },
      { path: "/admin/providers", slug: "admin-providers" },
      { path: "/admin/settings", slug: "admin-settings" },
      { path: "/admin/projects", slug: "admin-projects" },
    ],
  },
  {
    name: "supervisor", phone: "13000000003",
    pages: [
      { path: "/supervisor/workspace", slug: "supervisor-workspace" },
      { path: "/supervisor/cases", slug: "supervisor-cases" },
      { path: "/supervisor/case-alerts", slug: "supervisor-case-alerts" },
      { path: "/supervisor/discount-approvals", slug: "supervisor-discount-approvals" },
      { path: "/supervisor/legal-conversion-approvals", slug: "supervisor-legal-approvals" },
      { path: "/supervisor/escalated", slug: "supervisor-escalated" },
      { path: "/supervisor/team-performance", slug: "supervisor-team-performance" },
      { path: "/supervisor/live-wall", slug: "supervisor-live-wall" },
      { path: "/supervisor/script-labels", slug: "supervisor-script-labels" },
    ],
  },
  {
    name: "agent-internal", phone: "13000000004",
    pages: [
      { path: "/agent/workstation", slug: "agent-workstation" },
      { path: "/agent/cases", slug: "agent-cases" },
      { path: "/agent/call-history", slug: "agent-call-history" },
    ],
  },
  {
    name: "legal", phone: "13000000006",
    pages: [
      { path: "/legal/orders", slug: "legal-orders" },
      { path: "/legal/pending-finalize", slug: "legal-pending-finalize" },
    ],
  },
  {
    name: "coordinator", phone: "13000000007",
    pages: [
      { path: "/workorder/orders", slug: "workorder-orders" },
    ],
  },
  {
    name: "project-manager", phone: "13000000008",
    pages: [
      { path: "/pm/dashboard", slug: "pm-dashboard" },
    ],
  },
  {
    name: "provider-admin", phone: "13000000010",
    pages: [
      { path: "/provider/dashboard", slug: "provider-dashboard" },
      { path: "/provider/team", slug: "provider-team" },
      { path: "/provider/team-performance", slug: "provider-team-performance" },
      { path: "/provider/projects", slug: "provider-projects" },
    ],
  },
  {
    name: "provider-supervisor", phone: "13000000012",
    pages: [
      { path: "/provider/supervisor/workspace", slug: "provider-supervisor-workspace" },
    ],
  },
];

async function loginAs(page: Page, phone: string): Promise<void> {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  // 容忍角色登录后的「知道了」「下载 App」之类引导弹窗;最多关 3 次
  for (let i = 0; i < 3; i++) {
    const btn = page.getByRole("button", { name: "知道了" }).first();
    try {
      await btn.waitFor({ state: "visible", timeout: 1000 });
      await btn.click();
      await page.waitForTimeout(200);
    } catch {
      break;
    }
  }
}

interface PageReport {
  role: string;
  slug: string;
  url: string;
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  screenshotPath: string;
  finalUrl: string;
  capturedAt: string;
}

test.describe.serial("v0.5.6 vision-audit 截图收集", () => {
  test.setTimeout(45_000); // 单页 45s 兜底(网络 / 渲染慢)

  test.beforeAll(() => {
    if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  });

  for (const role of ROLE_SPECS) {
    for (const pg of role.pages) {
      test(`${role.name} → ${pg.slug}`, async ({ page }) => {
        const roleDir = path.join(OUTPUT_DIR, role.name);
        if (!fs.existsSync(roleDir)) fs.mkdirSync(roleDir, { recursive: true });

        const consoleErrors: string[] = [];
        const pageErrors: string[] = [];
        const failedRequests: string[] = [];
        page.on("console", (msg) => {
          if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 500));
        });
        page.on("pageerror", (e) => pageErrors.push(`${e.message}\n${(e.stack ?? "").slice(0, 400)}`));
        page.on("requestfailed", (r) => failedRequests.push(`${r.method()} ${r.url()} — ${r.failure()?.errorText}`));

        await loginAs(page, role.phone);
        await page.goto(pg.path);
        // networkidle 兜底 + 1s waiting,容忍长轮询的角色(督导 live-wall 等)
        await page.waitForLoadState("networkidle").catch(() => { /* noop */ });
        await page.waitForTimeout(1000);

        const screenshotPath = path.join(roleDir, `${pg.slug}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });

        const report: PageReport = {
          role: role.name,
          slug: pg.slug,
          url: pg.path,
          finalUrl: page.url(),
          consoleErrors,
          pageErrors,
          failedRequests,
          screenshotPath: path.relative(OUTPUT_DIR, screenshotPath),
          capturedAt: new Date().toISOString(),
        };
        fs.writeFileSync(
          path.join(roleDir, `${pg.slug}.json`),
          JSON.stringify(report, null, 2),
        );
      });
    }
  }
});
