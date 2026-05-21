#!/usr/bin/env node
// v0.5.7 — AI 视觉巡检改成纯本地版(不调任何 LLM API)
//
// 诱因:用户提供的 Gemini API key 被 GCP 拒绝访问,Claude key 没有,本期不强求
// 视觉模型分析。改成「**纯 Playwright + 机器能查的信号**」:
//
//   1. Playwright e2e:vision-collect 已跑 → 截图 + 旁边 .json 元数据
//      (consoleErrors / pageErrors / failedRequests / finalUrl)
//   2. 本脚本聚合 .json,识别下面 5 类「机器能查的」问题:
//      - 登录失败:finalUrl 跳到 /login 但 spec 不是 login 页 → HIGH
//      - 控制台错误(console.error)→ MEDIUM
//      - JS 异常(window.onerror / uncaught)→ HIGH
//      - 网络请求失败(过滤掉已知 telemetry 噪音)→ MEDIUM
//      - 截图疑似空白(文件 <10KB 可能是白屏)→ MEDIUM
//   3. axe-core a11y 检测(本地 Playwright,不收费)→ a11y-audit-report.json
//      集成到本报告作为补充
//
// 跑法:
//   node scripts/vision-audit-local-report.mjs
//
// 输出:vision-audit-report.md(根目录,.gitignore)

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUTPUT_DIR = path.resolve(__dirname, "../vision-audit-output");
const REPORT_PATH = path.resolve(__dirname, "../vision-audit-report.md");
const A11Y_PATH = path.resolve(__dirname, "../a11y-audit-report.json");

// 已知 telemetry / 第三方噪音,从 failedRequests 里 filter 掉
const NOISE_PATTERNS = [
  /telemetry\.refine\.dev/i,
  /google-analytics\.com/i,
  /googletagmanager\.com/i,
  /sentry\.io/i,
  /\/_debug\/client-error-beacon/i, // App webview 的 client-error-beacon 内网调试用
];

function isNoise(reqLine) {
  return NOISE_PATTERNS.some((p) => p.test(reqLine));
}

function isBlankScreenshot(pngPath) {
  if (!fs.existsSync(pngPath)) return false;
  const stats = fs.statSync(pngPath);
  // 1920×1080 全白 PNG 通常 < 5KB;有内容的页面 > 50KB
  return stats.size < 10_000;
}

function isLoginRedirect(meta) {
  if (!meta.finalUrl || !meta.url) return false;
  // finalUrl 含 /login 但请求的 url 不含 /login → 被重定向到登录页
  return meta.finalUrl.includes("/login") && !meta.url.includes("/login");
}

function walkOutputDir() {
  const entries = [];
  if (!fs.existsSync(OUTPUT_DIR)) {
    console.error(`❌ 输出目录不存在:${OUTPUT_DIR}。先跑 npm run e2e:vision-collect`);
    process.exit(1);
  }
  for (const role of fs.readdirSync(OUTPUT_DIR)) {
    const roleDir = path.join(OUTPUT_DIR, role);
    if (!fs.statSync(roleDir).isDirectory()) continue;
    for (const file of fs.readdirSync(roleDir)) {
      if (!file.endsWith(".json")) continue;
      const slug = file.replace(/\.json$/, "");
      try {
        const meta = JSON.parse(fs.readFileSync(path.join(roleDir, file), "utf-8"));
        const pngPath = path.join(roleDir, `${slug}.png`);
        entries.push({ role, slug, meta, pngPath });
      } catch (e) {
        console.error(`⚠ 解析 ${file} 失败:${e.message}`);
      }
    }
  }
  return entries;
}

function checkEntry(entry) {
  const { meta, pngPath } = entry;
  const issues = [];

  // 1. 登录失败 — HIGH(用户登录后无权访问 / 角色权限错)
  if (isLoginRedirect(meta)) {
    issues.push({
      severity: "HIGH",
      category: "auth",
      description: `登录失败:${meta.url} 被重定向到 ${meta.finalUrl}`,
      suggestion: "确认该角色账号是否有此页面权限;检查 auth-provider onError 是否在 401 时误踢",
    });
  }

  // 2. Page errors(JS uncaught)— HIGH
  if (meta.pageErrors?.length > 0) {
    for (const err of meta.pageErrors) {
      issues.push({
        severity: "HIGH",
        category: "js-exception",
        description: `JS 异常:${err.slice(0, 200)}`,
        suggestion: "看 stack trace 修对应组件 / API 返回",
      });
    }
  }

  // 3. Console errors — MEDIUM
  if (meta.consoleErrors?.length > 0) {
    for (const err of meta.consoleErrors) {
      issues.push({
        severity: "MEDIUM",
        category: "console-error",
        description: `Console:${err.slice(0, 200)}`,
        suggestion: "排查 React warning 或第三方 SDK 报错",
      });
    }
  }

  // 4. Failed requests(过滤 telemetry 噪音)— MEDIUM
  if (meta.failedRequests?.length > 0) {
    const real = meta.failedRequests.filter((r) => !isNoise(r));
    for (const req of real) {
      issues.push({
        severity: "MEDIUM",
        category: "network-failed",
        description: `请求失败:${req.slice(0, 200)}`,
        suggestion: "确认后端端点 / CORS / 权限守卫",
      });
    }
  }

  // 5. 截图疑似空白 — MEDIUM
  if (isBlankScreenshot(pngPath)) {
    const size = fs.statSync(pngPath).size;
    issues.push({
      severity: "MEDIUM",
      category: "blank-page",
      description: `截图大小 ${size}B,疑似白屏 / 渲染失败`,
      suggestion: "看 console errors;可能 React 组件 throw 没被 ErrorBoundary 捕到",
    });
  }

  return issues;
}

function readA11yReport() {
  if (!fs.existsSync(A11Y_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(A11Y_PATH, "utf-8"));
  } catch {
    return null;
  }
}

function severityRank(s) {
  return s === "HIGH" ? 0 : s === "MEDIUM" ? 1 : 2;
}

function main() {
  const entries = walkOutputDir();
  console.log(`▶ 共 ${entries.length} 张截图,本地聚合中...`);

  const results = entries.map((e) => ({ ...e, issues: checkEntry(e) }));

  const allIssues = results.flatMap((r) =>
    r.issues.map((i) => ({ role: r.role, slug: r.slug, ...i })),
  );
  const high = allIssues.filter((i) => i.severity === "HIGH");
  const medium = allIssues.filter((i) => i.severity === "MEDIUM");

  // a11y 报告(可选)
  const a11y = readA11yReport();
  const a11yViolations = a11y?.pages?.reduce(
    (sum, p) => sum + (p.violations?.length ?? 0), 0,
  ) ?? 0;

  // 生成 Markdown
  const lines = [];
  lines.push(`# 本地巡检报告 — ${new Date().toISOString().slice(0, 19).replace("T", " ")}`);
  lines.push("");
  lines.push("> v0.5.7 本地版(无 LLM 依赖):聚合 Playwright 截图旁的 .json 元数据,识别");
  lines.push("> 5 类「机器能查的」问题:登录失败 / JS 异常 / Console 错误 / 网络失败 / 白屏。");
  lines.push("> a11y 部分由 axe-core 在 4 关键页跑 WCAG 2.1 A+AA。");
  lines.push("");
  lines.push("## 摘要");
  lines.push("");
  lines.push(`- 截图数:${entries.length}`);
  lines.push(`- 问题数:**${allIssues.length}**(HIGH **${high.length}** / MEDIUM **${medium.length}**)`);
  if (a11y) {
    lines.push(`- a11y 违规:**${a11yViolations}** 条(${a11y.pages.length} 页)`);
  } else {
    lines.push(`- a11y:未跑(${A11Y_PATH} 不存在,跑 \`npm run e2e:a11y\` 后再聚合)`);
  }
  lines.push("");

  // HIGH 优先
  if (high.length > 0) {
    lines.push(`## HIGH(${high.length})`);
    lines.push("");
    for (const it of high) {
      lines.push(`- **${it.role}/${it.slug}** [${it.category}] ${it.description}`);
      lines.push(`  - 建议:${it.suggestion}`);
    }
    lines.push("");
  }

  if (medium.length > 0) {
    lines.push(`## MEDIUM(${medium.length})`);
    lines.push("");
    for (const it of medium) {
      lines.push(`- **${it.role}/${it.slug}** [${it.category}] ${it.description}`);
      lines.push(`  - 建议:${it.suggestion}`);
    }
    lines.push("");
  }

  // 按页详列(包括 ✅ 无问题)
  lines.push("## 按角色 + 页详列");
  lines.push("");
  for (const r of results) {
    const issues = r.issues.sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
    lines.push(`### ${r.role} / ${r.slug}(${r.meta.finalUrl ?? r.meta.url ?? "?"})`);
    lines.push("");
    if (issues.length === 0) {
      lines.push("✅ 无问题");
    } else {
      for (const it of issues) {
        lines.push(`- **[${it.severity}/${it.category}]** ${it.description}`);
        lines.push(`  - ${it.suggestion}`);
      }
    }
    lines.push("");
  }

  // a11y 详列
  if (a11y && a11y.pages?.length > 0) {
    lines.push("## a11y 详细(axe-core WCAG 2.1 A+AA)");
    lines.push("");
    for (const p of a11y.pages) {
      lines.push(`### ${p.name}(${p.url})`);
      lines.push("");
      if (p.violations.length === 0) {
        lines.push("✅ 无 a11y 违规");
      } else {
        for (const v of p.violations) {
          lines.push(`- **[${v.impact ?? "?"}] ${v.id}** ${v.help}(${v.nodes} 节点)`);
          lines.push(`  - ${v.description}`);
          lines.push(`  - 文档:${v.helpUrl}`);
        }
      }
      lines.push("");
    }
  }

  fs.writeFileSync(REPORT_PATH, lines.join("\n"), "utf-8");
  console.log(`\n✓ 报告写入 ${REPORT_PATH}`);
  console.log(`  HIGH:${high.length} · MEDIUM:${medium.length} · a11y 违规:${a11yViolations}`);
}

main();
