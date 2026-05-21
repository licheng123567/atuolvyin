/**
 * all-role-detail-audit.spec.ts
 * 全角色详情页 + 表单页巡检：14 个账号 × 角色能访问的 /:id 详情路由 + /new 表单路由
 * 目标：跑完全部、产出清单，不因个别失败中断。
 * 运行：cd frontend && npx playwright test e2e/all-role-detail-audit.spec.ts --project=chromium --reporter=list --workers=1
 */
import { test, expect, type Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
interface PageIssues {
  /** How we arrived: e.g. "admin/cases 列表→详情" or "/admin/users/new 表单" */
  entryPath: string;
  /** The final URL that was audited */
  auditedUrl: string;
  pageErrors: string[];
  consoleErrors: string[];
  failedRequests: Array<{ url: string; status: number }>;
  redirectedToLogin: boolean;
  isBlankPage: boolean;
  rootText: string;
  skipped: boolean;
  skipReason?: string;
}

interface RoleDetailResult {
  roleName: string;
  phone: string;
  pages: PageIssues[];
  loginFailed: boolean;
  loginError?: string;
}

// Global collector
const DETAIL_AUDIT_RESULTS: RoleDetailResult[] = [];

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
async function dismissAppIntroIfPresent(page: Page) {
  try {
    const closeBtn = page.getByRole("button", { name: "知道了" });
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
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 15_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAppIntroIfPresent(page);
}

function isHarmlessConsoleError(msg: string): boolean {
  const lower = msg.toLowerCase();
  if (lower.includes("source map") || lower.includes("sourcemap")) return true;
  if (lower.includes("favicon") && lower.includes("404")) return true;
  if (lower.includes("extension") || lower.includes("chrome-extension")) return true;
  if (lower.includes("[vite]") && lower.includes("hmr")) return true;
  return false;
}

/**
 * 启动监听器（在 goto 前调用），返回收集器对象（引用语义，goto 后读取结果）
 */
function startListeners(page: Page) {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: Array<{ url: string; status: number }> = [];

  const onPageError = (err: Error) => pageErrors.push(err.message);
  const onConsole = (msg: { type: () => string; text: () => string }) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (!isHarmlessConsoleError(text)) consoleErrors.push(text);
    }
  };
  const onResponse = (r: { status: () => number; url: () => string }) => {
    const status = r.status();
    if (status >= 400) failedRequests.push({ url: r.url(), status });
  };

  page.on("pageerror", onPageError);
  page.on("console", onConsole);
  page.on("response", onResponse);

  return {
    pageErrors,
    consoleErrors,
    failedRequests,
    stop: () => {
      page.removeListener("pageerror", onPageError);
      page.removeListener("console", onConsole);
      page.removeListener("response", onResponse);
    },
  };
}

async function collectPageState(
  page: Page,
  collectors: ReturnType<typeof startListeners>,
  entryPath: string,
): Promise<PageIssues> {
  const currentUrl = page.url();
  const redirectedToLogin = currentUrl.includes("/login");
  let isBlankPage = false;
  let rootText = "";
  try {
    rootText = (await page.locator("#root").innerText({ timeout: 3000 })).trim();
    isBlankPage = rootText.length < 10;
  } catch {
    isBlankPage = true;
    rootText = "(#root not found or timeout)";
  }
  collectors.stop();
  return {
    entryPath,
    auditedUrl: currentUrl,
    pageErrors: [...collectors.pageErrors],
    consoleErrors: [...collectors.consoleErrors],
    failedRequests: [...collectors.failedRequests],
    redirectedToLogin,
    isBlankPage,
    rootText: rootText.slice(0, 200),
    skipped: false,
  };
}

/**
 * 直接访问 URL，采集问题。不抛异常。
 */
async function auditDirectUrl(page: Page, url: string, entryPath: string): Promise<PageIssues> {
  const collectors = startListeners(page);
  try {
    await page.goto(url, { timeout: 20_000, waitUntil: "domcontentloaded" });
    await dismissAppIntroIfPresent(page);
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  } catch (e) {
    collectors.pageErrors.push(`NAVIGATION ERROR: ${String(e)}`);
  }
  return collectPageState(page, collectors, entryPath);
}

/**
 * 从列表页点进第一行详情，采集详情页问题。
 * listUrl: 要打开的列表页
 * buttonTexts: 按钮文本候选列表，按顺序尝试（第一个匹配的生效）
 * rowSelector: 若所有 buttonTexts 都找不到，尝试点第一个匹配的行元素（行本身可点击）
 * preGotoSetup: goto 之前可执行的 page 操作（如改日期 filter）
 */
async function auditViaListClick(
  page: Page,
  listUrl: string,
  entryDesc: string,
  buttonTexts: string[],
  options: {
    rowSelector?: string;  // fallback: click first matching row/element
    waitAfterNav?: number;
    /** Extra URL params to append (e.g. "?date_from=2020-01-01&date_to=2099-01-01") */
    extraParams?: string;
  } = {},
): Promise<PageIssues> {
  const fullUrl = options.extraParams ? `${listUrl}${options.extraParams}` : listUrl;

  // 先打开列表页
  const listCollectors = startListeners(page);
  try {
    await page.goto(fullUrl, { timeout: 20_000, waitUntil: "domcontentloaded" });
    await dismissAppIntroIfPresent(page);
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  } catch (e) {
    listCollectors.pageErrors.push(`NAVIGATION ERROR: ${String(e)}`);
  }
  listCollectors.stop();

  // 检查列表页是否正常
  const listUrl2 = page.url();
  if (listUrl2.includes("/login")) {
    return {
      entryPath: entryDesc,
      auditedUrl: listUrl2,
      pageErrors: ["列表页被重定向到 /login"],
      consoleErrors: [],
      failedRequests: [],
      redirectedToLogin: true,
      isBlankPage: false,
      rootText: "",
      skipped: false,
    };
  }

  // 等待数据出现：networkidle 已经等过了，再额外等 1s 确保 React 渲染完成
  await page.waitForTimeout(1000);

  // 尝试找详情按钮（精确文本匹配，取第一个可见）
  let foundBtn: import("@playwright/test").Locator | null = null;
  for (const text of buttonTexts) {
    try {
      // 先尝试 role=button 精确名称匹配
      const exact = page.getByRole("button", { name: text, exact: true }).first();
      if (await exact.isVisible({ timeout: 1500 })) {
        foundBtn = exact;
        break;
      }
    } catch { /* try next */ }
    try {
      // 再尝试包含匹配（覆盖带图标的按钮：文本可能是 "详情" 但按钮还有 SVG）
      const candidate = page.locator(`button, a`).filter({ hasText: text }).first();
      if (await candidate.isVisible({ timeout: 1500 })) {
        foundBtn = candidate;
        break;
      }
    } catch { /* try next */ }
  }

  // 如果没找到按钮，尝试点行元素（行本身可点击的卡片布局）
  if (!foundBtn && options.rowSelector) {
    try {
      const row = page.locator(options.rowSelector).first();
      if (await row.isVisible({ timeout: 1500 })) {
        foundBtn = row;
      }
    } catch {
      // pass
    }
  }

  if (!foundBtn) {
    // 检查是否真的是空列表
    let emptyText = "";
    try {
      emptyText = (await page.locator("#root").innerText({ timeout: 2000 })).trim().slice(0, 100);
    } catch {
      emptyText = "(未能获取)";
    }
    // 尝试提取更具体的空态文本
    const emptyIndicators = ["暂无", "无数据", "无记录", "暂无数据", "No data"];
    const hasEmptyIndicator = emptyIndicators.some((s) => emptyText.includes(s));
    return {
      entryPath: entryDesc,
      auditedUrl: page.url(),
      pageErrors: [],
      consoleErrors: [],
      failedRequests: [...listCollectors.failedRequests],
      redirectedToLogin: false,
      isBlankPage: false,
      rootText: emptyText,
      skipped: true,
      skipReason: hasEmptyIndicator
        ? `列表为空（"${emptyText.slice(0, 60)}"）`
        : `未找到详情入口按钮（候选文本：${buttonTexts.join("/")}）；列表内容长度=${emptyText.length}`,
    };
  }

  // 点击并监听详情页
  const detailCollectors = startListeners(page);
  try {
    await Promise.all([
      page.waitForNavigation({ timeout: 12_000, waitUntil: "domcontentloaded" }).catch(() => {}),
      foundBtn.click(),
    ]);
    await dismissAppIntroIfPresent(page);
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    if (options.waitAfterNav) {
      await page.waitForTimeout(options.waitAfterNav);
    }
  } catch (e) {
    detailCollectors.pageErrors.push(`CLICK/NAV ERROR: ${String(e)}`);
  }

  return collectPageState(page, detailCollectors, entryDesc);
}

// ─────────────────────────────────────────────────────────────────────────────
// 单角色巡检任务定义
// ─────────────────────────────────────────────────────────────────────────────
interface DetailTask {
  /** 入口描述（出现在报告里） */
  desc: string;
  /** 执行函数 — 传入已登录的 page，返回 PageIssues */
  run: (page: Page) => Promise<PageIssues>;
}

// 公共 helper: 直接 goto /new 表单
function formTask(url: string): DetailTask {
  return {
    desc: `${url} (表单)`,
    run: (page) => auditDirectUrl(page, url, `${url} (表单)`),
  };
}

// 公共 helper: 列表→详情
function listDetailTask(
  listUrl: string,
  desc: string,
  buttonTexts: string[],
  opts: { rowSelector?: string } = {},
): DetailTask {
  return {
    desc,
    run: (page) => auditViaListClick(page, listUrl, desc, buttonTexts, opts),
  };
}

// ── 平台超管 tasks ────────────────────────────────────────────────
const SUPERADMIN_TASKS: DetailTask[] = [
  // 详情页
  listDetailTask("/ops/tenants", "/ops/tenants 列表→详情", ["详情"]),
  listDetailTask("/ops/providers", "/ops/providers 列表→详情", ["详情", "查看"]),
  // 表单页
  formTask("/ops/tenants/new"),
  formTask("/ops/providers/new"),
];

// ── 平台运营员 tasks ──────────────────────────────────────────────
const OPS_TASKS: DetailTask[] = [
  listDetailTask("/ops/tenants", "/ops/tenants 列表→详情", ["详情"]),
  listDetailTask("/ops/providers", "/ops/providers 列表→详情", ["详情", "查看"]),
  formTask("/ops/tenants/new"),
  formTask("/ops/providers/new"),
];

// ── 物业管理员 tasks ──────────────────────────────────────────────
const ADMIN_PROPERTY_TASKS: DetailTask[] = [
  // 详情页（从列表进）
  listDetailTask("/admin/cases", "/admin/cases 列表→案件详情", ["详情"]),
  listDetailTask("/admin/users", "/admin/users 列表→编辑", ["编辑"]),
  listDetailTask("/admin/settlements", "/admin/settlements 列表→结算明细", ["查看明细"]),
  // admin/providers 行本身可点击（无独立按钮），用 rowSelector 点第一个 cursor-pointer 行
  listDetailTask("/admin/providers", "/admin/providers 列表→合作服务商详情", [], {
    rowSelector: "tbody tr.cursor-pointer",
  }),
  listDetailTask("/admin/discount-approvals", "/admin/discount-approvals 列表→减免详情", ["查看", "详情"]),
  // legal-conversion 行本身可点击（cursor-pointer），无独立按钮文字
  listDetailTask("/admin/legal-conversion", "/admin/legal-conversion 列表→法务转化详情", [], {
    rowSelector: "tbody tr.cursor-pointer",
  }),
  listDetailTask("/admin/agent-commissions", "/admin/agent-commissions 列表→提成明细", ["查看明细"]),
  // 表单页
  formTask("/admin/users/new"),
  formTask("/admin/projects/new"),
  formTask("/admin/risk-keywords/new"),
  formTask("/workorder/orders/new"),
];

// ── 督导 tasks ────────────────────────────────────────────────────
const SUPERVISOR_TASKS: DetailTask[] = [
  // supervisor/cases 是 div card 布局，按钮文字是"详情"，包含 Eye 图标
  listDetailTask("/supervisor/cases", "/supervisor/cases 列表→案件详情", ["详情"]),
  listDetailTask("/supervisor/discount-approvals", "/supervisor/discount-approvals 列表→减免详情", [
    "查看", "详情",
  ]),
  // supervisor/reviews 按钮文字是"复核"（pending）或"查看"（已完成）
  listDetailTask("/supervisor/reviews", "/supervisor/reviews 列表→质检详情", ["复核", "查看"]),
];

// ── 内勤催收员 tasks ──────────────────────────────────────────────
const AGENT_INTERNAL_TASKS: DetailTask[] = [
  listDetailTask("/agent/cases", "/agent/cases 列表→工作台", ["处理", "查看", "详情"]),
  // call-history 默认只显示今日；加宽日期范围确保能看到 seed 数据
  listDetailTask(
    "/agent/call-history",
    "/agent/call-history 列表→通话详情",
    ["查看转写", "查看详情"],
    { extraParams: "?date_from=2020-01-01&date_to=2099-12-31" },
  ),
  formTask("/workorder/orders/new"),
];

// ── 外勤催收员 tasks —— 同内勤（路由相同）
const AGENT_EXTERNAL_TASKS = AGENT_INTERNAL_TASKS;

// ── 物业法务 tasks ────────────────────────────────────────────────
const LEGAL_PROPERTY_TASKS: DetailTask[] = [
  // legal/internal-orders: pending 状态显示"处理"按钮，其他状态显示"详情"按钮
  listDetailTask("/legal/internal-orders", "/legal/internal-orders 列表→详情", [
    "处理", "详情", "查看",
  ]),
];

// ── 协调员 tasks ──────────────────────────────────────────────────
const COORDINATOR_TASKS: DetailTask[] = [
  listDetailTask("/workorder/orders", "/workorder/orders 列表→工单详情", ["处理", "查看", "详情"]),
  formTask("/workorder/orders/new"),
];

// ── 项目经理-物业侧 tasks ─────────────────────────────────────────
const PM_PROPERTY_TASKS: DetailTask[] = [
  listDetailTask("/admin/cases", "/admin/cases 列表→案件详情 (PM视角)", ["详情"]),
];

// ── 项目经理-服务商侧 tasks ───────────────────────────────────────
const PM_PROVIDER_TASKS: DetailTask[] = [
  // PM dashboard 无列表详情入口；检测服务商结算详情（若有权限）
  {
    desc: "/pm/dashboard (直接访问)",
    run: (page) => auditDirectUrl(page, "/pm/dashboard", "/pm/dashboard (直接访问)"),
  },
];

// ── 服务商管理员 tasks ────────────────────────────────────────────
const ADMIN_PROVIDER_TASKS: DetailTask[] = [
  listDetailTask("/provider/settlements", "/provider/settlements 列表→结算明细", [
    "查看明细", "详情", "查看",
  ]),
  // 表单页
  // Provider admin 没有独立 new 表单，provider/team 只看列表
];

// ── 服务商催收员 tasks —— 同内勤催收员
const AGENT_PROVIDER_TASKS = AGENT_INTERNAL_TASKS;

// ── 服务商督导 tasks —— 同物业督导
const SUPERVISOR_PROVIDER_TASKS = SUPERVISOR_TASKS;

// ── 服务商法务 tasks ──────────────────────────────────────────────
const LEGAL_PROVIDER_TASKS: DetailTask[] = [
  listDetailTask(
    "/provider/legal/cases",
    "/provider/legal/cases 列表→案件详情",
    ["查看", "详情"],
  ),
  listDetailTask(
    "/provider/legal/requests",
    "/provider/legal/requests 列表→请求详情",
    ["查看", "详情"],
  ),
];

// ─────────────────────────────────────────────────────────────────────────────
// 角色定义
// ─────────────────────────────────────────────────────────────────────────────
interface RoleDetailDef {
  name: string;
  phone: string;
  tasks: DetailTask[];
}

const ROLE_DETAIL_DEFS: RoleDetailDef[] = [
  { name: "superadmin (13000000000)", phone: "13000000000", tasks: SUPERADMIN_TASKS },
  { name: "ops 运营员 (13000000001)", phone: "13000000001", tasks: OPS_TASKS },
  { name: "admin 物业管理员 (13000000002)", phone: "13000000002", tasks: ADMIN_PROPERTY_TASKS },
  { name: "supervisor 督导 (13000000003)", phone: "13000000003", tasks: SUPERVISOR_TASKS },
  { name: "agent 内勤催收员 (13000000004)", phone: "13000000004", tasks: AGENT_INTERNAL_TASKS },
  { name: "agent 外勤催收员 (13000000005)", phone: "13000000005", tasks: AGENT_EXTERNAL_TASKS },
  { name: "legal 物业法务 (13000000006)", phone: "13000000006", tasks: LEGAL_PROPERTY_TASKS },
  { name: "coordinator 协调员 (13000000007)", phone: "13000000007", tasks: COORDINATOR_TASKS },
  { name: "project_manager 物业PM (13000000008)", phone: "13000000008", tasks: PM_PROPERTY_TASKS },
  { name: "project_manager 服务商PM (13000000009)", phone: "13000000009", tasks: PM_PROVIDER_TASKS },
  { name: "admin 服务商管理员 (13000000010)", phone: "13000000010", tasks: ADMIN_PROVIDER_TASKS },
  { name: "agent 服务商催收员 (13000000011)", phone: "13000000011", tasks: AGENT_PROVIDER_TASKS },
  { name: "supervisor 服务商督导 (13000000012)", phone: "13000000012", tasks: SUPERVISOR_PROVIDER_TASKS },
  { name: "legal 服务商法务 (13000000013)", phone: "13000000013", tasks: LEGAL_PROVIDER_TASKS },
];

// ─────────────────────────────────────────────────────────────────────────────
// Build describes dynamically
// ─────────────────────────────────────────────────────────────────────────────
for (const roleDef of ROLE_DETAIL_DEFS) {
  test.describe(`详情巡检: ${roleDef.name}`, () => {
    let roleResult: RoleDetailResult;

    test.beforeAll(async () => {
      roleResult = {
        roleName: roleDef.name,
        phone: roleDef.phone,
        pages: [],
        loginFailed: false,
      };
      DETAIL_AUDIT_RESULTS.push(roleResult);
    });

    for (const task of roleDef.tasks) {
      test(`${roleDef.name} → ${task.desc}`, async ({ page }) => {
        // Login
        try {
          await login(page, roleDef.phone);
        } catch (e) {
          if (!roleResult.loginFailed) {
            roleResult.loginFailed = true;
            roleResult.loginError = String(e);
          }
          roleResult.pages.push({
            entryPath: task.desc,
            auditedUrl: "",
            pageErrors: [`LOGIN FAILED: ${String(e)}`],
            consoleErrors: [],
            failedRequests: [],
            redirectedToLogin: true,
            isBlankPage: true,
            rootText: "",
            skipped: false,
          });
          return;
        }

        let issues: PageIssues;
        try {
          issues = await task.run(page);
        } catch (e) {
          issues = {
            entryPath: task.desc,
            auditedUrl: page.url(),
            pageErrors: [`TASK ERROR: ${String(e)}`],
            consoleErrors: [],
            failedRequests: [],
            redirectedToLogin: false,
            isBlankPage: true,
            rootText: "",
            skipped: false,
          };
        }
        roleResult.pages.push(issues);

        if (issues.skipped) {
          // Skipped — don't assert, just record
          return;
        }

        // ── Hard assertions ──────────────────────────────────────
        expect(
          issues.pageErrors,
          `[${roleDef.name}] ${task.desc}: 存在未捕获 JS 异常`,
        ).toHaveLength(0);

        const serverErrors = issues.failedRequests.filter((r) => r.status >= 500);
        expect(
          serverErrors,
          `[${roleDef.name}] ${task.desc}: 存在 5xx 服务端错误`,
        ).toHaveLength(0);

        expect(
          issues.redirectedToLogin,
          `[${roleDef.name}] ${task.desc}: 被重定向回 /login`,
        ).toBe(false);
      });
    }

    test.afterAll(() => {
      printRoleDetailResult(roleResult);
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Final summary test (runs last)
// ─────────────────────────────────────────────────────────────────────────────
test.describe("🗂️ 详情页+表单页巡检汇总", () => {
  test("打印全量结构化报告", async () => {
    printFullDetailReport(DETAIL_AUDIT_RESULTS);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Severity helpers
// ─────────────────────────────────────────────────────────────────────────────
function pageSeverity(p: PageIssues): "red" | "yellow" | "skip" | "clean" {
  if (p.skipped) return "skip";
  if (
    p.pageErrors.length > 0 ||
    p.redirectedToLogin ||
    p.isBlankPage ||
    p.failedRequests.some((r) => r.status >= 500)
  ) return "red";
  if (p.consoleErrors.length > 0 || p.failedRequests.length > 0) return "yellow";
  return "clean";
}

// ─────────────────────────────────────────────────────────────────────────────
// Reporting
// ─────────────────────────────────────────────────────────────────────────────
function printRoleDetailResult(r: RoleDetailResult) {
  const lines: string[] = [];
  lines.push(`\n${"═".repeat(72)}`);
  lines.push(`角色: ${r.roleName}  手机: ${r.phone}`);
  if (r.loginFailed) lines.push(`  ⛔ 登录失败: ${r.loginError ?? "unknown"}`);
  for (const p of r.pages) {
    const sev = pageSeverity(p);
    const icon = sev === "red" ? "🔴" : sev === "yellow" ? "🟡" : sev === "skip" ? "⏭️" : "✅";
    lines.push(`  ${icon} ${p.entryPath}`);
    if (p.skipped) {
      lines.push(`      → SKIP: ${p.skipReason ?? "未知原因"}`);
      continue;
    }
    lines.push(`      → 最终URL: ${p.auditedUrl}`);
    if (p.redirectedToLogin) lines.push(`      → 被踢回 /login`);
    if (p.isBlankPage) lines.push(`      → 白屏 (rootText: "${p.rootText.slice(0, 80)}")`);
    for (const e of p.pageErrors) lines.push(`      [pageerror] ${e.slice(0, 200)}`);
    for (const e of p.consoleErrors) lines.push(`      [console.error] ${e.slice(0, 200)}`);
    for (const req of p.failedRequests) {
      const icon2 = req.status >= 500 ? "🔴" : "🟡";
      lines.push(`      ${icon2} HTTP ${req.status} ${req.url}`);
    }
  }
  console.log(lines.join("\n"));
}

function printFullDetailReport(results: RoleDetailResult[]) {
  const lines: string[] = [];
  lines.push("\n");
  lines.push("╔══════════════════════════════════════════════════════════════════════════╗");
  lines.push("║         详情页 + 表单页全角色巡检报告 — all-role-detail-audit.spec.ts        ║");
  lines.push("╚══════════════════════════════════════════════════════════════════════════╝");

  let totalPages = 0;
  let cleanPages = 0;
  let redPages = 0;
  let yellowPages = 0;
  let skippedPages = 0;
  const redItems: Array<{ role: string; path: string; url: string; details: string[] }> = [];
  const yellowItems: Array<{ role: string; path: string; url: string; details: string[] }> = [];
  const skipItems: Array<{ role: string; path: string; reason: string }> = [];

  for (const r of results) {
    for (const p of r.pages) {
      totalPages++;
      const sev = pageSeverity(p);
      if (sev === "skip") {
        skippedPages++;
        skipItems.push({ role: r.roleName, path: p.entryPath, reason: p.skipReason ?? "—" });
      } else if (sev === "red") {
        redPages++;
        const details: string[] = [];
        if (p.redirectedToLogin) details.push("鉴权失效：被重定向至 /login");
        if (p.isBlankPage) details.push(`白屏 (root内容: "${p.rootText.slice(0, 80)}")`);
        for (const e of p.pageErrors) details.push(`未捕获异常: ${e.slice(0, 200)}`);
        for (const req of p.failedRequests.filter((x) => x.status >= 500)) {
          details.push(`5xx: HTTP ${req.status} ${req.url}`);
        }
        redItems.push({ role: r.roleName, path: p.entryPath, url: p.auditedUrl, details });
      } else if (sev === "yellow") {
        yellowPages++;
        const details: string[] = [];
        for (const e of p.consoleErrors) details.push(`console.error: ${e.slice(0, 200)}`);
        for (const req of p.failedRequests) {
          const tag =
            req.status >= 500
              ? "5xx"
              : req.status === 401
                ? "401(未授权)"
                : req.status === 403
                  ? "403(无权)"
                  : `${req.status}`;
          details.push(`${tag}: ${req.url}`);
        }
        yellowItems.push({ role: r.roleName, path: p.entryPath, url: p.auditedUrl, details });
      } else {
        cleanPages++;
      }
    }
  }

  const totalRoles = results.length;
  lines.push(`\n总览: ${totalRoles} 角色`);
  lines.push(`  巡检页面总数: ${totalPages}（含跳过 ${skippedPages} 条）`);
  lines.push(`  ✅ 干净页面: ${cleanPages}`);
  lines.push(`  🔴 严重问题: ${redPages} 页`);
  lines.push(`  🟡 警告问题: ${yellowPages} 页`);
  lines.push(`  ⏭️ 跳过: ${skippedPages} 页`);

  // 🔴 严重问题
  lines.push("\n─────────────────────────────────────────────────────────────────────");
  lines.push("🔴 严重问题（白屏 / 未捕获异常 / 掉登录页 / 5xx）");
  lines.push("─────────────────────────────────────────────────────────────────────");
  if (redItems.length === 0) {
    lines.push("  （无）");
  } else {
    for (const item of redItems) {
      lines.push(`  角色: ${item.role}`);
      lines.push(`  入口: ${item.path}`);
      lines.push(`  URL:  ${item.url}`);
      for (const d of item.details) lines.push(`    • ${d}`);
      lines.push("");
    }
  }

  // 🟡 警告问题
  lines.push("─────────────────────────────────────────────────────────────────────");
  lines.push("🟡 警告问题（console error / 4xx）");
  lines.push("─────────────────────────────────────────────────────────────────────");
  if (yellowItems.length === 0) {
    lines.push("  （无）");
  } else {
    for (const item of yellowItems) {
      lines.push(`  角色: ${item.role}`);
      lines.push(`  入口: ${item.path}`);
      lines.push(`  URL:  ${item.url}`);
      for (const d of item.details) lines.push(`    • ${d}`);
      lines.push("");
    }
  }

  // ⏭️ 跳过原因
  lines.push("─────────────────────────────────────────────────────────────────────");
  lines.push("⏭️ 跳过记录（列表为空 / 未找到详情入口）");
  lines.push("─────────────────────────────────────────────────────────────────────");
  if (skipItems.length === 0) {
    lines.push("  （无）");
  } else {
    for (const item of skipItems) {
      lines.push(`  角色: ${item.role}`);
      lines.push(`  入口: ${item.path}`);
      lines.push(`  原因: ${item.reason.slice(0, 120)}`);
      lines.push("");
    }
  }

  // 角色 × 页面 完整清单
  lines.push("─────────────────────────────────────────────────────────────────────");
  lines.push("角色 × 页面 完整清单");
  lines.push("─────────────────────────────────────────────────────────────────────");
  for (const r of results) {
    lines.push(`\n${r.roleName} (${r.phone})`);
    if (r.loginFailed) {
      lines.push(`  ⛔ 登录失败: ${r.loginError ?? "unknown"}`);
      continue;
    }
    for (const p of r.pages) {
      const sev = pageSeverity(p);
      const icon = sev === "red" ? "🔴" : sev === "yellow" ? "🟡" : sev === "skip" ? "⏭️" : "✅";
      lines.push(`  ${icon} ${p.entryPath}`);
    }
  }

  lines.push("\n══════════════════════════════════════════════════════════════════════\n");
  console.log(lines.join("\n"));
}
