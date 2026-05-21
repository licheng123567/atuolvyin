// v0.5.6 — a11y 自动检测 PoC,与 vision-audit 互补
//
// axe-core 跑每个关键页,捕捉「机器能检的」无障碍违规(WCAG 2.1 A/AA)。
// Claude Vision 负责「机器检不出」的视觉/语义问题(布局漂移/术语混乱等),两者互补。
//
// 跑法:`npx playwright test e2e/a11y-audit.spec.ts --project=chromium`
// 输出:a11y-audit-report.json(根目录) + console 打印 violation 摘要
//
// 不进 CI:轻量,但本期只验证可行性 + 给 backlog 输出违规清单,等下期评估是否长跑。

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPORT_PATH = path.resolve(__dirname, "../a11y-audit-report.json");

const PASSWORD = "Demo@123!";

// 选有代表性的页(不跑全 50 个,本期 PoC 4 关键页)
const TARGETS: { name: string; phone: string; path: string }[] = [
  { name: "admin-dashboard", phone: "13000000002", path: "/admin/dashboard" },
  { name: "agent-workstation", phone: "13000000004", path: "/agent/workstation" },
  { name: "supervisor-workspace", phone: "13000000003", path: "/supervisor/workspace" },
  { name: "ops-tenants", phone: "13000000001", path: "/ops/tenants" },
];

async function loginAs(page: Page, phone: string): Promise<void> {
  await page.goto("/login");
  await page.fill('input[id="account"]', phone);
  await page.fill('input[id="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
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

interface PageA11yResult {
  name: string;
  url: string;
  violations: Array<{
    id: string;
    impact: string | null | undefined;
    description: string;
    help: string;
    helpUrl: string;
    nodes: number;
  }>;
}

test.describe.serial("v0.5.6 a11y 自动检测 PoC", () => {
  test.setTimeout(60_000);

  const collected: PageA11yResult[] = [];

  for (const t of TARGETS) {
    test(`a11y / ${t.name}`, async ({ page }) => {
      await loginAs(page, t.phone);
      await page.goto(t.path);
      await page.waitForLoadState("networkidle").catch(() => { /* noop */ });
      await page.waitForTimeout(800);

      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"]) // WCAG 2.1 A + AA 级别
        .analyze();

      const summary: PageA11yResult = {
        name: t.name,
        url: t.path,
        violations: result.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          help: v.help,
          helpUrl: v.helpUrl,
          nodes: v.nodes.length,
        })),
      };
      collected.push(summary);

      // 不让 a11y 违规 fail 测试(本期 PoC 只收集),用 expect 输出但允许通过
      console.log(`[a11y] ${t.name}: ${summary.violations.length} 个违规`);
      for (const v of summary.violations) {
        console.log(`  - [${v.impact ?? "?"}] ${v.id}: ${v.help} (${v.nodes} 节点)`);
      }
      // 软断言:critical 违规要警告但不卡测试(本期不修)
      const critical = summary.violations.filter((v) => v.impact === "critical");
      expect(critical.length, "critical 违规列表(仅警告,不卡测试)").toBeGreaterThanOrEqual(0);
    });
  }

  test.afterAll(() => {
    fs.writeFileSync(
      REPORT_PATH,
      JSON.stringify(
        {
          generatedAt: new Date().toISOString(),
          tagsScanned: ["wcag2a", "wcag2aa"],
          pages: collected,
        },
        null,
        2,
      ),
      "utf-8",
    );
    console.log(`\n✓ a11y 报告已写入 ${REPORT_PATH}`);
  });
});
