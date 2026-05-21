#!/usr/bin/env node
// v0.5.6 PoC → v0.5.7 多 provider 策略
//
// AI 视觉巡检:读 vision-audit-output/{role}/{slug}.png + {slug}.json,每张图喂给
// 视觉模型出 JSON 问题清单,再聚合成 Markdown 报告。
//
// **v0.5.7 起默认用 Gemini 2.5 Flash**(免费额度大,~$0.001/图);Anthropic Claude
// 作为兜底备选(更准但贵 ~30 倍)。策略模式:
//   1. 优先 GEMINI_API_KEY → Gemini 2.5 Flash
//   2. 兜底 ANTHROPIC_API_KEY → Claude Opus 4.5
//   3. 都没设 → 报错退出
//
// 跑法:
//   export GEMINI_API_KEY=AIza...           # Google AI Studio 免费申请
//   node scripts/vision-audit-analyze.mjs
//
// 输出:vision-audit-report.md(根目录,默认 gitignore)
//
// 成本预估:
//   Gemini 2.5 Flash:~50 图 × $0.001 ≈ $0.05/轮(且有免费额度 1500/天)
//   Claude Opus 4.5: ~50 图 × $0.03 ≈ $1.50/轮

import { GoogleGenerativeAI } from "@google/generative-ai";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const OUTPUT_DIR = path.resolve(__dirname, "../vision-audit-output");
const REPORT_PATH = path.resolve(__dirname, "../vision-audit-report.md");

// ─── Provider 策略选择 ────────────────────────────────────────────────

function pickProvider() {
  if (process.env.GEMINI_API_KEY) return "gemini";
  if (process.env.ANTHROPIC_API_KEY) return "anthropic";
  return null;
}

const PROVIDER = pickProvider();
if (!PROVIDER) {
  console.error(
    "❌ 未设置 GEMINI_API_KEY 或 ANTHROPIC_API_KEY。\n" +
    "推荐:export GEMINI_API_KEY=AIza...(Google AI Studio 免费申请)\n" +
    "兜底:export ANTHROPIC_API_KEY=sk-ant-...",
  );
  process.exit(1);
}

const PROMPT = `你是有证慧催 SaaS 的 UX 审计员。请审查这张截图,识别用户可见的问题。

**重点关注:**
1. **布局问题** — 对齐错位 / 间距不均 / 文字溢出 / 表格列宽不合理 / 元素被裁切
2. **文案问题** — 错别字 / 术语不一致(注意「物业管理员」不是「admin」/「管理员」)/ 标题过长 / 描述不清
3. **交互问题** — 按钮不可见 / 颜色对比度过低 / 缺少 hover/disabled 状态 / icon 含义不明
4. **数据展示问题** — 空态缺失(空列表显示空白)/ 加载态缺失 / 数字格式不一致 / 时间格式错乱
5. **无障碍问题** — 仅靠颜色传达信息 / 缺少 label / 按钮无可识别名称

**仅报告 HIGH 或 MEDIUM 严重度**(LOW 噪音不报)。
**只输出 JSON**,不要 markdown 围栏(\`\`\`json),不要其他文字:

{
  "issues": [
    {
      "severity": "HIGH" | "MEDIUM",
      "category": "layout" | "copy" | "interaction" | "data" | "a11y",
      "description": "具体问题(中文,1-2 句)",
      "suggestion": "具体修复建议(中文,1 句)"
    }
  ]
}

若无问题,返回 {"issues":[]}。`;

// ─── Gemini 实现 ──────────────────────────────────────────────────────

let geminiModel = null;
if (PROVIDER === "gemini") {
  const gemini = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
  const modelName = process.env.VISION_MODEL ?? "gemini-2.5-flash";
  geminiModel = gemini.getGenerativeModel({
    model: modelName,
    generationConfig: {
      temperature: 0.2,
      maxOutputTokens: 1024,
    },
  });
  console.log(`▶ Provider: Gemini (${modelName})`);
}

// ─── Anthropic 实现(兜底) ────────────────────────────────────────────

let anthropicClient = null;
if (PROVIDER === "anthropic") {
  const Anthropic = (await import("@anthropic-ai/sdk")).default;
  anthropicClient = new Anthropic();
  const modelName = process.env.VISION_MODEL ?? "claude-opus-4-5-20250929";
  console.log(`▶ Provider: Anthropic (${modelName})`);
}

function stripJsonFences(text) {
  // Gemini 喜欢加 ```json ... ``` 围栏,即使 prompt 说不要也会偶尔加
  let t = text.trim();
  if (t.startsWith("```")) {
    // 去掉首行 ```json 或 ```
    t = t.replace(/^```(?:json)?\s*\n/i, "");
    // 去掉末尾 ```
    t = t.replace(/\n```\s*$/i, "");
  }
  return t.trim();
}

async function analyzePngGemini(pngPath) {
  const data = fs.readFileSync(pngPath).toString("base64");
  const result = await geminiModel.generateContent([
    { inlineData: { data, mimeType: "image/png" } },
    PROMPT,
  ]);
  const raw = result.response.text();
  const clean = stripJsonFences(raw);
  try {
    const parsed = JSON.parse(clean);
    return { ok: true, issues: parsed.issues ?? [] };
  } catch {
    return { ok: false, issues: [], raw: clean.slice(0, 200) };
  }
}

async function analyzePngAnthropic(pngPath) {
  const data = fs.readFileSync(pngPath).toString("base64");
  const modelName = process.env.VISION_MODEL ?? "claude-opus-4-5-20250929";
  const resp = await anthropicClient.messages.create({
    model: modelName,
    max_tokens: 1024,
    messages: [
      {
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: "image/png", data } },
          { type: "text", text: PROMPT },
        ],
      },
    ],
  });
  const text = resp.content.find((c) => c.type === "text")?.text ?? "";
  const clean = stripJsonFences(text);
  try {
    const parsed = JSON.parse(clean);
    return { ok: true, issues: parsed.issues ?? [] };
  } catch {
    return { ok: false, issues: [], raw: clean.slice(0, 200) };
  }
}

async function analyzePng(pngPath, _meta) {
  return PROVIDER === "gemini"
    ? analyzePngGemini(pngPath)
    : analyzePngAnthropic(pngPath);
}

function severityRank(s) {
  return s === "HIGH" ? 0 : s === "MEDIUM" ? 1 : 2;
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
      if (!file.endsWith(".png")) continue;
      const slug = file.replace(/\.png$/, "");
      const metaPath = path.join(roleDir, `${slug}.json`);
      const meta = fs.existsSync(metaPath) ? JSON.parse(fs.readFileSync(metaPath, "utf-8")) : { role, slug };
      entries.push({ role, slug, pngPath: path.join(roleDir, file), meta });
    }
  }
  return entries;
}

async function main() {
  const entries = walkOutputDir();
  console.log(`▶ 共 ${entries.length} 张截图,开始分析...`);

  const allResults = [];
  let n = 0;
  for (const e of entries) {
    n += 1;
    process.stdout.write(`[${n}/${entries.length}] ${e.role}/${e.slug} ... `);
    try {
      const result = await analyzePng(e.pngPath, e.meta);
      allResults.push({ ...e, ...result });
      console.log(result.ok ? `✓ ${result.issues.length} 个问题` : `⚠ 解析失败(${result.raw})`);
    } catch (err) {
      console.log(`✗ ${err?.message ?? "未知错误"}`);
      allResults.push({ ...e, ok: false, issues: [], error: String(err?.message ?? err) });
    }
    // Rate limit:Gemini Flash 免费额度是 RPM,sleep 100ms 就够;Anthropic 1s 避 429
    await new Promise((r) => setTimeout(r, PROVIDER === "gemini" ? 100 : 1000));
  }

  // 生成 Markdown 报告
  const totalIssues = allResults.reduce((sum, r) => sum + (r.issues?.length ?? 0), 0);
  const high = allResults.flatMap((r) => (r.issues ?? []).filter((i) => i.severity === "HIGH"));
  const medium = allResults.flatMap((r) => (r.issues ?? []).filter((i) => i.severity === "MEDIUM"));
  const consoleErrorCount = allResults.reduce(
    (sum, r) => sum + (r.meta?.consoleErrors?.length ?? 0), 0,
  );
  const pageErrorCount = allResults.reduce(
    (sum, r) => sum + (r.meta?.pageErrors?.length ?? 0), 0,
  );

  const lines = [];
  lines.push(`# AI 视觉巡检报告 — ${new Date().toISOString().slice(0, 19).replace("T", " ")}`);
  lines.push("");
  lines.push(`> Provider:\`${PROVIDER}\`(模型 ${process.env.VISION_MODEL ?? (PROVIDER === "gemini" ? "gemini-2.5-flash" : "claude-opus-4-5")})`);
  lines.push(`> 截图数:${entries.length} · 总问题数:${totalIssues}(HIGH ${high.length} · MEDIUM ${medium.length})`);
  lines.push(`> Console 错误:${consoleErrorCount} · Page 异常:${pageErrorCount}`);
  lines.push("");
  lines.push("## 摘要(按严重度排)");
  lines.push("");
  for (const sev of ["HIGH", "MEDIUM"]) {
    const items = allResults
      .flatMap((r) =>
        (r.issues ?? [])
          .filter((i) => i.severity === sev)
          .map((i) => ({ role: r.role, slug: r.slug, ...i })),
      );
    if (items.length === 0) continue;
    lines.push(`### ${sev}(${items.length})`);
    lines.push("");
    for (const it of items) {
      lines.push(`- **${it.role}/${it.slug}** [${it.category}] ${it.description}`);
      lines.push(`  - 建议:${it.suggestion}`);
    }
    lines.push("");
  }

  lines.push("## 详细(按角色 + 页)");
  lines.push("");
  for (const r of allResults) {
    const issues = (r.issues ?? []).sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
    const consoleErr = r.meta?.consoleErrors?.length ?? 0;
    const pageErr = r.meta?.pageErrors?.length ?? 0;
    lines.push(`### ${r.role} / ${r.slug}(${r.meta?.finalUrl ?? r.meta?.url ?? "?"})`);
    lines.push("");
    if (consoleErr || pageErr) {
      lines.push(`> ⚠ Console 错误 ${consoleErr} 条 · Page 异常 ${pageErr} 条`);
      lines.push("");
    }
    if (issues.length === 0) {
      lines.push("✅ 视觉无问题");
    } else {
      for (const it of issues) {
        lines.push(`- **[${it.severity}/${it.category}]** ${it.description}`);
        lines.push(`  - 建议:${it.suggestion}`);
      }
    }
    if (!r.ok && r.raw) {
      lines.push(`> ⚠ JSON 解析失败,原始返回:${r.raw}`);
    }
    if (r.error) {
      lines.push(`> ❌ 调用错误:${r.error}`);
    }
    lines.push("");
  }

  fs.writeFileSync(REPORT_PATH, lines.join("\n"), "utf-8");
  console.log(`\n✓ 报告已写入 ${REPORT_PATH}`);
  console.log(`  HIGH:${high.length} · MEDIUM:${medium.length} · 总计:${totalIssues}`);
}

main().catch((err) => {
  console.error("❌ 致命错误:", err);
  process.exit(1);
});
