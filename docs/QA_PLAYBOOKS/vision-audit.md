# AI 视觉巡检 / a11y 自动检测 — v0.5.7

> 「**手动跑 + 出报告**」流程,把每次需要肉眼盯一遍的角色巡检变成机器+模型的工作。
> 用户原话:「有没有什么工具或者调用其他模型,通过模拟操作浏览器操作来判断哪些地方有问题,
> 哪个地方需要优化,减少人工测试。」**v0.5.7 起默认用 Gemini 2.5 Flash**,~$0.05/轮,
> 有免费额度 1500 RPM(够跑很多轮);Anthropic Claude 作为兜底备选。

## 整体流程

```
Playwright 截图收集       视觉模型分析                聚合输出
─────────────────         ─────────────────             ─────────
50 张全屏 PNG       →     每图 1 次 API 调用      →     vision-audit-report.md
+ 50 份 JSON 元数据        (Gemini ~$0.001/图)            + a11y-audit-report.json
(console/page error)        (Claude ~$0.03/图)
```

两个互补:
- **视觉模型(Gemini / Claude)**:看「**机器查不出的**」— 布局漂移 / 术语混乱 / 数字格式不一致 / 空态缺失 / 按钮含义不明
- **axe-core a11y**:看「**机器能查的**」— 颜色对比度 / 缺 label / 图像无 alt / 焦点顺序 / WCAG 2.1 A+AA

## 跑法

### 第 1 步:本地起 backend + frontend(用 e2e 端口)

```bash
# 后端 :18100(非 reload 模式,e2e 标准端口)
cd poc/backend
python3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 18100

# 前端 :5273
cd frontend
npm run dev -- --port 5273 --strictPort --mode e2e
```

或直接 `npm run e2e:vision-collect` 让 Playwright 自动拉起(playwright.config.ts 的 webServer 配置)。

### 第 2 步:跑截图收集(~5 分钟)

```bash
cd frontend
npm run e2e:vision-collect
```

产物:`frontend/vision-audit-output/{role}/{slug}.{png,json}`。每张 PNG 是某角色登录后该页的全屏截图;同名 JSON 是该页的 console error / pageerror / 失败网络请求清单。

### 第 3 步:调视觉模型出报告(~3-5 分钟)

**推荐:Gemini 2.5 Flash(便宜 + 免费额度)**

```bash
# 1. 申请 Google AI Studio key(免费):https://aistudio.google.com/apikey
export GEMINI_API_KEY=AIza...
# 2. 跑分析(脚本自动检测 provider)
node scripts/vision-audit-analyze.mjs
# 或:
npm run vision:analyze
```

**兜底:Claude Opus 4.5(精度更高但更贵)**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
node scripts/vision-audit-analyze.mjs    # 自动 fallback 到 Anthropic
```

provider 选择策略:`GEMINI_API_KEY` 优先 → `ANTHROPIC_API_KEY` 兜底 → 都没设则报错退出。
可用 `VISION_MODEL` 环境变量覆盖默认模型(如 `gemini-2.5-pro` / `claude-sonnet-4-5`)。

产物:`frontend/vision-audit-report.md`。结构:
- 顶部摘要:provider + 模型 + 总问题数 / HIGH / MEDIUM / Console 错误数 / Page 异常数
- 按严重度分组(HIGH 优先)
- 按角色 + 页详列(每页的所有问题 + console/page error 计数)

### 第 4 步(可选):跑 a11y 检测

```bash
cd frontend
npm run e2e:a11y
```

产物:`frontend/a11y-audit-report.json` + console 输出违规摘要。本期 PoC 跑 4 个代表性页(admin-dashboard / agent-workstation / supervisor-workspace / ops-tenants),够定性看 WCAG 违规分布,**不作为质量门禁**。

## 调参

`vision-audit-analyze.mjs` 默认用 `claude-opus-4-5-20250929`。换 Sonnet 更便宜但 vision 精度低:

```bash
VISION_MODEL=claude-sonnet-4-5 node scripts/vision-audit-analyze.mjs
```

如果误报多,改 prompt — 编辑 `scripts/vision-audit-analyze.mjs` 的 `PROMPT` 常量,加更多约束(如「不要报字体粗细差异」「不要报 1px 对齐」等)。

## 成本预估

**Gemini 2.5 Flash(默认,v0.5.7 起)**:

| 项 | 单价 | 量 | 小计 |
|---|---|---|---|
| Gemini 2.5 Flash vision input | $0.075 / MTok | ~50 张 × ~2K tok | ~$0.008 |
| Gemini 2.5 Flash output | $0.30 / MTok | ~50 × ~500 tok | ~$0.008 |
| **单次完整跑总计** | | | **~$0.05** |

且 Google AI Studio 有免费额度 1500 RPM(每分钟 1500 请求),日常跑足够覆盖。

**Claude Opus 4.5(兜底)**:

| 项 | 单价 | 量 | 小计 |
|---|---|---|---|
| Claude Opus 4.5 vision input | $15 / MTok | ~50 张 × ~2.5K tok | ~$1.85 |
| Claude Opus 4.5 vision output | $75 / MTok | ~50 × ~500 tok | ~$1.90 |
| **单次完整跑总计** | | | **~$4** |

跑频率建议:**手动按需**(发版前 / 大改后);**不进 CI**(模型 false positive 让开发者疲于反驳)。

## 不进 CI 的理由

- ~5 分钟跑时间放进 PR check 太重(虽然 Gemini 成本已经几乎免费)
- vision 模型的 false positive 会让开发者疲于反驳
- 比较好的位置:**发版冒烟 checklist** 的一个手动步骤,人来决定是否要修

## 为什么不用 Percy / Chromatic

考虑过,放弃理由:

- **Percy** 是像素 diff(已有 `v200-mobile-pixel-diff.spec.ts` 在做),不报告 UX 问题
- **Chromatic** 走 Storybook,我们没有 Storybook
- **Claude Vision** 直接读截图 + 出自然语言问题清单,跟我们的 Playwright 已有基础设施衔接成本最低

## 已知局限

- ❌ vision 模型看不到**交互流畅度**(动画卡 / 按钮响应延迟)— 这部分继续靠人手测
- ❌ 报告里的 false positive 需要人工过滤 — 不是「直接照单修」
- ❌ 截图是单帧,**业务流程跨页**的问题看不出来(比如「确认按钮点了之后跳转出错」需要 E2E 测试覆盖)

## 与其他 e2e 套件的关系

| 套件 | 作用 | 何时跑 |
|---|---|---|
| `smoke.spec.ts` | 14 角色登录 + 首屏不白 | 每次 PR(CI) |
| `per-role-pages.spec.ts` / `all-role-audit.spec.ts` | 关键页 console error / 404 / blank | 每次 PR(CI) |
| `v200-mobile-pixel-diff.spec.ts` | 移动端 5 屏像素 diff(WebView) | 手动 |
| `vision-audit-collect.spec.ts` + `vision-audit-analyze.mjs` | **AI UX 审计**(本文) | 手动按需 |
| `a11y-audit.spec.ts` | WCAG 违规扫描 | 手动按需 |

## TODO / 下期可能改进

- [ ] 跑 prompt 校准:实测一轮后看 false positive 比例,调约束
- [ ] 加 diff 模式:只分析与上次报告相比新增的问题(降噪)
- [ ] 集成到 finishing-a-development-branch 流程作为可选步骤
- [ ] 支持只跑某个角色 / 某些页(用环境变量过滤)
