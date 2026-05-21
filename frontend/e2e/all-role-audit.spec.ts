/**
 * all-role-audit.spec.ts
 * 全角色巡检：14 个账号 × 角色所有侧栏导航页，收集运行时问题并产出结构化清单。
 * 目标：跑完全部、产出清单，不因个别失败中断。
 * 运行：cd frontend && npx playwright test e2e/all-role-audit.spec.ts --project=chromium --reporter=list --workers=1
 */
import { test, expect, Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
interface PathIssues {
  path: string;
  pageErrors: string[];
  consoleErrors: string[];
  failedRequests: Array<{ url: string; status: number }>;
  redirectedToLogin: boolean;
  isBlankPage: boolean;
  rootText: string;
}

interface RoleAuditResult {
  roleName: string;
  phone: string;
  paths: PathIssues[];
  loginFailed: boolean;
  loginError?: string;
}

// Global collector — all results accumulated across describes
const AUDIT_RESULTS: RoleAuditResult[] = [];

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
async function dismissAppIntroIfPresent(page: Page) {
  const closeBtn = page.getByRole("button", { name: "知道了" });
  try {
    await closeBtn.waitFor({ state: "visible", timeout: 2500 });
    await closeBtn.click();
    await closeBtn.waitFor({ state: "hidden", timeout: 2000 });
  } catch {
    // 不存在，忽略
  }
}

async function login(page: Page, phone: string): Promise<void> {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), {
      timeout: 15_000,
    }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAppIntroIfPresent(page);
}

/**
 * 判断是否是无害噪音（不需要记录的 console error）。
 * 过滤 favicon 404、第三方 source map 警告等。
 */
function isHarmlessConsoleError(msg: string): boolean {
  const lower = msg.toLowerCase();
  // source map 警告
  if (lower.includes("source map") || lower.includes("sourcemap")) return true;
  // favicon 404
  if (lower.includes("favicon") && lower.includes("404")) return true;
  // Extension inject
  if (lower.includes("extension") || lower.includes("chrome-extension")) return true;
  // Vite HMR / websocket dev noise
  if (lower.includes("[vite]") && lower.includes("hmr")) return true;
  return false;
}

/**
 * 访问单个 path，收集所有问题。
 * 不抛异常 — 将所有问题存入 PathIssues。
 */
async function auditPath(page: Page, path: string): Promise<PathIssues> {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: Array<{ url: string; status: number }> = [];

  // 注意：listener 需要在 goto 前注册
  const onPageError = (err: Error) => pageErrors.push(err.message);
  const onConsole = (msg: { type: () => string; text: () => string }) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (!isHarmlessConsoleError(text)) {
        consoleErrors.push(text);
      }
    }
  };
  const onResponse = (r: { status: () => number; url: () => string }) => {
    const status = r.status();
    if (status >= 400) {
      // 记录 4xx 和 5xx；4xx 区分 401（鉴权）/ 403（权限）/ 其他
      failedRequests.push({ url: r.url(), status });
    }
  };

  page.on("pageerror", onPageError);
  page.on("console", onConsole);
  page.on("response", onResponse);

  try {
    // 带查询参数的 path（如 /legal/internal-orders?tab=escalated）直接 goto
    await page.goto(path, { timeout: 20_000, waitUntil: "domcontentloaded" });
    await dismissAppIntroIfPresent(page);
    // 等网络空闲最多 10s（某些页面长轮询，不能死等）
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {
      /* 超时时继续，已有的数据足够判断 */
    });
  } catch (e) {
    pageErrors.push(`NAVIGATION ERROR: ${String(e)}`);
  }

  // 是否被踢回 /login
  const currentUrl = page.url();
  const redirectedToLogin = currentUrl.includes("/login");

  // 检查白屏：#root 内文本近乎为空
  let isBlankPage = false;
  let rootText = "";
  try {
    rootText = (await page.locator("#root").innerText({ timeout: 3000 })).trim();
    // 少于 10 个字符视为白屏（空白 / 只剩个空容器）
    isBlankPage = rootText.length < 10;
  } catch {
    isBlankPage = true;
    rootText = "(#root not found or timeout)";
  }

  // 移除 listener，防止污染下一次
  page.removeListener("pageerror", onPageError);
  page.removeListener("console", onConsole);
  page.removeListener("response", onResponse);

  return {
    path,
    pageErrors,
    consoleErrors,
    failedRequests,
    redirectedToLogin,
    isBlankPage,
    rootText: rootText.slice(0, 200),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Role definitions — derived from src/config/nav.ts + App.tsx
// ─────────────────────────────────────────────────────────────────────────────

interface RoleDef {
  name: string;
  phone: string;
  paths: string[];
}

// 路径去重工具
function uniq(arr: string[]): string[] {
  return [...new Set(arr)];
}

// Help path common to all roles
const HELP_PATH = "/help/app";

// ── 平台超管 (superadmin) ─────────────────────────────────────────────────
const SUPERADMIN_PATHS = uniq([
  "/ops/tenants",
  "/ops/providers",
  "/ops/settlements",
  "/ops/law-firms",
  "/ops/legal-workstation",
  "/ops/announcements",
  "/super/health",
  "/super/audit",
  "/super/cost",
  "/super/plans",
  "/super/llm-prompts",
  "/super/blockchain-config",
  HELP_PATH,
]);

// ── 平台运营员 (ops) ─────────────────────────────────────────────────────
const OPS_PATHS = uniq([
  "/ops/tenants",
  "/ops/tenants/trial",
  "/ops/customer-followups",
  "/ops/providers",
  "/ops/settlements",
  "/ops/law-firms",
  "/ops/legal-workstation",
  "/ops/announcements",
  "/ops/audit-logs",
  HELP_PATH,
]);

// ── 物业管理员 (admin, tenant-side) ─────────────────────────────────────
const ADMIN_PROPERTY_PATHS = uniq([
  "/admin/projects",
  "/admin/dashboard",
  "/admin/cases",
  "/admin/cases/kanban",
  "/admin/pool",
  "/admin/cases/import",
  "/admin/users",
  "/admin/agent-devices",
  "/admin/providers",
  "/admin/settlements",
  "/admin/reports",
  "/admin/compliance",
  "/admin/scripts",
  "/admin/scripts/effectiveness",
  "/admin/risk-keywords",
  "/admin/legal-conversion",
  "/admin/legal-conversion-approvals",
  "/admin/partner-law-firms",
  "/admin/internal-letter-templates",
  "/admin/discount-approvals",
  "/admin/agent-commissions",
  "/admin/audit-logs",
  "/admin/settings",
  HELP_PATH,
]);

// ── 督导 (supervisor) ────────────────────────────────────────────────────
const SUPERVISOR_PATHS = uniq([
  "/supervisor/workspace",
  "/supervisor/live-wall",
  "/supervisor/team-performance",
  "/admin/agent-devices",
  "/supervisor/cases",
  "/supervisor/escalated",
  "/supervisor/promises",
  "/supervisor/case-alerts",
  "/supervisor/discount-approvals",
  "/supervisor/legal-conversion-approvals",
  "/supervisor/reviews",
  "/supervisor/script-labels",
  "/supervisor/risk-events",
  "/supervisor/training",
  "/supervisor/my-kpi",
  "/supervisor/shifts",
  "/supervisor/stats",
  HELP_PATH,
]);

// ── 催收员 (agent) ───────────────────────────────────────────────────────
const AGENT_PATHS = uniq([
  "/agent/workstation",
  "/agent/cases",
  "/agent/call-history",
  "/agent/profile",
  HELP_PATH,
]);

// ── 物业法务 (legal, tenant-side) ────────────────────────────────────────
const LEGAL_PROPERTY_PATHS = uniq([
  "/legal/internal-orders",
  "/legal/internal-orders?tab=escalated",
  HELP_PATH,
]);

// ── 协调员 (coordinator) ─────────────────────────────────────────────────
const COORDINATOR_PATHS = uniq([
  "/workorder/orders",
  HELP_PATH,
]);

// ── 项目经理-物业侧 (project_manager, tenant-side) ────────────────────
const PM_PROPERTY_PATHS = uniq([
  "/pm/dashboard",
  "/supervisor/live-wall",
  HELP_PATH,
]);

// ── 项目经理-服务商侧 (project_manager, provider-side) ───────────────
const PM_PROVIDER_PATHS = uniq([
  "/pm/dashboard",
  HELP_PATH,
]);

// ── 服务商管理员 (admin, provider-side) ──────────────────────────────
const ADMIN_PROVIDER_PATHS = uniq([
  "/provider/dashboard",
  "/provider/projects",
  "/provider/tenants",
  "/provider/team",
  "/provider/team-performance",
  "/provider/scripts",
  "/provider/settlements",
  "/provider/historical-reports",
  HELP_PATH,
]);

// ── 服务商催收员 (agent, provider external) ─────────────────────────
// Same menu as property agent
const AGENT_PROVIDER_PATHS = AGENT_PATHS;

// ── 服务商督导 (supervisor, provider-side) ──────────────────────────
// Uses same supervisor nav as property-side supervisor
const SUPERVISOR_PROVIDER_PATHS = SUPERVISOR_PATHS;

// ── 服务商法务 (legal, provider-side) ───────────────────────────────
const LEGAL_PROVIDER_PATHS = uniq([
  "/provider/legal/cases",
  "/provider/legal/requests",
  HELP_PATH,
]);

const ROLE_DEFS: RoleDef[] = [
  { name: "superadmin (13000000000)", phone: "13000000000", paths: SUPERADMIN_PATHS },
  { name: "ops 运营员 (13000000001)", phone: "13000000001", paths: OPS_PATHS },
  { name: "admin 物业管理员 (13000000002)", phone: "13000000002", paths: ADMIN_PROPERTY_PATHS },
  { name: "supervisor 督导 (13000000003)", phone: "13000000003", paths: SUPERVISOR_PATHS },
  { name: "agent 内勤催收员 (13000000004)", phone: "13000000004", paths: AGENT_PATHS },
  { name: "agent 外勤催收员 (13000000005)", phone: "13000000005", paths: AGENT_PATHS },
  { name: "legal 物业法务 (13000000006)", phone: "13000000006", paths: LEGAL_PROPERTY_PATHS },
  { name: "coordinator 协调员 (13000000007)", phone: "13000000007", paths: COORDINATOR_PATHS },
  { name: "project_manager 物业PM (13000000008)", phone: "13000000008", paths: PM_PROPERTY_PATHS },
  { name: "project_manager 服务商PM (13000000009)", phone: "13000000009", paths: PM_PROVIDER_PATHS },
  { name: "admin 服务商管理员 (13000000010)", phone: "13000000010", paths: ADMIN_PROVIDER_PATHS },
  { name: "agent 服务商催收员 (13000000011)", phone: "13000000011", paths: AGENT_PROVIDER_PATHS },
  { name: "supervisor 服务商督导 (13000000012)", phone: "13000000012", paths: SUPERVISOR_PROVIDER_PATHS },
  { name: "legal 服务商法务 (13000000013)", phone: "13000000013", paths: LEGAL_PROVIDER_PATHS },
];

// ─────────────────────────────────────────────────────────────────────────────
// Build describes dynamically
// ─────────────────────────────────────────────────────────────────────────────
for (const roleDef of ROLE_DEFS) {
  test.describe(`巡检: ${roleDef.name}`, () => {
    // Per-describe result bucket
    let roleResult: RoleAuditResult;

    test.beforeAll(async () => {
      roleResult = {
        roleName: roleDef.name,
        phone: roleDef.phone,
        paths: [],
        loginFailed: false,
      };
      // Register in global results immediately so it appears even if tests don't run
      AUDIT_RESULTS.push(roleResult);
    });

    for (const path of roleDef.paths) {
      test(`${roleDef.name} → ${path}`, async ({ page }) => {
        // Login each test (new page context per test)
        try {
          await login(page, roleDef.phone);
        } catch (e) {
          // Login failed — mark and skip path audit, but don't throw
          if (!roleResult.loginFailed) {
            roleResult.loginFailed = true;
            roleResult.loginError = String(e);
          }
          // Create a stub entry so the path appears in the report
          roleResult.paths.push({
            path,
            pageErrors: [`LOGIN FAILED: ${String(e)}`],
            consoleErrors: [],
            failedRequests: [],
            redirectedToLogin: true,
            isBlankPage: true,
            rootText: "",
          });
          // Soft-fail: don't assert, just return
          return;
        }

        const issues = await auditPath(page, path);
        roleResult.paths.push(issues);

        // ── Hard assertions (真正 fatal，失败才 fail 测试) ──────────
        // 1. 未捕获 JS 异常 — 严重
        expect(
          issues.pageErrors,
          `[${roleDef.name}] ${path}: 存在未捕获 JS 异常`
        ).toHaveLength(0);

        // 2. 5xx 服务端错误 — 严重
        const serverErrors = issues.failedRequests.filter((r) => r.status >= 500);
        expect(
          serverErrors,
          `[${roleDef.name}] ${path}: 存在 5xx 服务端错误`
        ).toHaveLength(0);

        // 3. 被踢回 /login — 严重（鉴权失效）
        expect(
          issues.redirectedToLogin,
          `[${roleDef.name}] ${path}: 被重定向回 /login`
        ).toBe(false);

        // ── 软记录（不 fail 测试，但出现在清单） ─────────────────
        // 白屏、console error、4xx 均已收入 issues，供报告使用
      });
    }

    test.afterAll(() => {
      // 打印该角色完整巡检结果到 console（list reporter 会输出）
      printRoleResult(roleResult);
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Final summary test (runs last)
// ─────────────────────────────────────────────────────────────────────────────
test.describe("🗂️ 巡检汇总", () => {
  test("打印全量结构化报告", async () => {
    // 等所有 role describe 完成后汇总（在 --workers=1 下，顺序执行保证有结果）
    printFullReport(AUDIT_RESULTS);
    // 这个 test 本身永远 pass — 目的只是产出报告
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Reporting helpers
// ─────────────────────────────────────────────────────────────────────────────
function printRoleResult(r: RoleAuditResult) {
  const lines: string[] = [];
  lines.push(`\n${"═".repeat(72)}`);
  lines.push(`角色: ${r.roleName}  手机: ${r.phone}`);
  if (r.loginFailed) {
    lines.push(`  ⛔ 登录失败: ${r.loginError ?? "unknown"}`);
  }
  for (const p of r.paths) {
    const sev = pathSeverity(p);
    const icon = sev === "red" ? "🔴" : sev === "yellow" ? "🟡" : "✅";
    lines.push(`  ${icon} ${p.path}`);
    if (p.redirectedToLogin) lines.push(`      → 被踢回 /login`);
    if (p.isBlankPage) lines.push(`      → 白屏 (rootText: "${p.rootText}")`);
    for (const e of p.pageErrors) lines.push(`      [pageerror] ${e}`);
    for (const e of p.consoleErrors) lines.push(`      [console.error] ${e}`);
    for (const req of p.failedRequests) {
      const icon2 = req.status >= 500 ? "🔴" : req.status === 401 ? "🟡" : "🟡";
      lines.push(`      ${icon2} HTTP ${req.status} ${req.url}`);
    }
  }
  console.log(lines.join("\n"));
}

function pathSeverity(p: PathIssues): "red" | "yellow" | "clean" {
  if (
    p.pageErrors.length > 0 ||
    p.redirectedToLogin ||
    p.isBlankPage ||
    p.failedRequests.some((r) => r.status >= 500)
  ) {
    return "red";
  }
  if (p.consoleErrors.length > 0 || p.failedRequests.length > 0) {
    return "yellow";
  }
  return "clean";
}

function printFullReport(results: RoleAuditResult[]) {
  const lines: string[] = [];
  lines.push("\n");
  lines.push("╔══════════════════════════════════════════════════════════════════════╗");
  lines.push("║              全角色巡检报告 — all-role-audit.spec.ts               ║");
  lines.push("╚══════════════════════════════════════════════════════════════════════╝");

  // 总览
  let totalPaths = 0;
  let cleanPaths = 0;
  let redPaths = 0;
  let yellowPaths = 0;
  const redItems: Array<{ role: string; path: string; details: string[] }> = [];
  const yellowItems: Array<{ role: string; path: string; details: string[] }> = [];

  for (const r of results) {
    for (const p of r.paths) {
      totalPaths++;
      const sev = pathSeverity(p);
      if (sev === "red") {
        redPaths++;
        const details: string[] = [];
        if (p.redirectedToLogin) details.push("鉴权失效：被重定向至 /login");
        if (p.isBlankPage) details.push(`白屏 (root内容: "${p.rootText.slice(0, 80)}")`);
        for (const e of p.pageErrors) details.push(`未捕获异常: ${e.slice(0, 200)}`);
        for (const req of p.failedRequests.filter((x) => x.status >= 500)) {
          details.push(`5xx: HTTP ${req.status} ${req.url}`);
        }
        redItems.push({ role: r.roleName, path: p.path, details });
      } else if (sev === "yellow") {
        yellowPaths++;
        const details: string[] = [];
        for (const e of p.consoleErrors) details.push(`console.error: ${e.slice(0, 200)}`);
        for (const req of p.failedRequests) {
          const tag = req.status >= 500 ? "5xx" : req.status === 401 ? "401(未授权)" : req.status === 403 ? "403(无权)" : `${req.status}`;
          details.push(`${tag}: ${req.url}`);
        }
        yellowItems.push({ role: r.roleName, path: p.path, details });
      } else {
        cleanPaths++;
      }
    }
  }

  const totalRoles = results.length;
  lines.push(`\n总览: ${totalRoles} 角色 × ${totalPaths} 页`);
  lines.push(`  ✅ 干净页面: ${cleanPaths}`);
  lines.push(`  🔴 严重问题: ${redPaths} 页`);
  lines.push(`  🟡 警告问题: ${yellowPaths} 页`);

  // 🔴 严重问题
  lines.push("\n─────────────────────────────────────────────────────────────────────");
  lines.push("🔴 严重问题（白屏 / 未捕获异常 / 掉登录页 / 5xx）");
  lines.push("─────────────────────────────────────────────────────────────────────");
  if (redItems.length === 0) {
    lines.push("  （无）");
  } else {
    for (const item of redItems) {
      lines.push(`  角色: ${item.role}`);
      lines.push(`  路径: ${item.path}`);
      for (const d of item.details) lines.push(`    • ${d}`);
      lines.push("");
    }
  }

  // 🟡 警告问题
  lines.push("─────────────────────────────────────────────────────────────────────");
  lines.push("🟡 警告问题（console error / 4xx — 区分疑似真问题 vs 预期）");
  lines.push("─────────────────────────────────────────────────────────────────────");
  if (yellowItems.length === 0) {
    lines.push("  （无）");
  } else {
    for (const item of yellowItems) {
      lines.push(`  角色: ${item.role}`);
      lines.push(`  路径: ${item.path}`);
      for (const d of item.details) lines.push(`    • ${d}`);
      lines.push("");
    }
  }

  // 角色详情
  lines.push("─────────────────────────────────────────────────────────────────────");
  lines.push("角色 × 路径 完整清单");
  lines.push("─────────────────────────────────────────────────────────────────────");
  for (const r of results) {
    lines.push(`\n${r.roleName} (${r.phone})`);
    if (r.loginFailed) {
      lines.push(`  ⛔ 登录失败: ${r.loginError ?? "unknown"}`);
      continue;
    }
    for (const p of r.paths) {
      const sev = pathSeverity(p);
      const icon = sev === "red" ? "🔴" : sev === "yellow" ? "🟡" : "✅";
      lines.push(`  ${icon} ${p.path}`);
    }
  }

  lines.push("\n══════════════════════════════════════════════════════════════════════\n");
  console.log(lines.join("\n"));
}
