# UI 还原状态（2026-05-07）

## 背景

`ui/` 目录的 HTML 原型分两类：

1. **v1.0 时期原始设计稿（5 个）**：`login.html`、`admin.html`、`supervisor.html`、`agent-pc.html`、`platform-superadmin.html`、`platform-ops.html`、`provider-admin.html`、`legal.html`、`workorder.html`、`payment-h5.html`、`app-agent.html`、`index.html`。HTML 先于 React 实现，是设计基准；React 实现可能存在 1:1 还原差异。
2. **v1.4/v1.5 反向出原型（14 个）**：详见 `docs/UI_PROTOTYPE_GAPS.md`。HTML 由 React 反向产出，结构天然对齐；视觉差异主要在颜色 token 等细节。

## 本次（v1.5 release-ready）已还原

| 页面 | 还原前 | 还原后 |
|---|---|---|
| `login` | 居中卡片简约版 | 双面板设计：左暗色品牌渐变 + 4 大特性 + 右表单（密码可见切换 + 「记住此设备」语义沿用 sessionStorage 横幅） |

## 经评估「天然对齐」无需还原

下列 React 页面的 HTML 原型是 v1.4/v1.5 期间从 React 反向产出的，结构与设计 token 完全一致：

- `supervisor/live-wall` ↔ `supervisor.html#sv-livewall`
- `help/app` ↔ `help-app.html`
- `verify` ↔ `verify.html`
- `agent/workstation/live` + `admin/workstation/live` ↔ `agent-workstation-live.html` + `admin-workstation-live.html`
- `supervisor/reviews/detail` ↔ `supervisor-review-detail.html`
- `supervisor/risk-events` ↔ `supervisor-risk-events.html`
- `admin/scripts/effectiveness` ↔ `admin-scripts-effectiveness.html`
- `admin/scripts/versions` ↔ `admin-scripts-versions.html`
- `admin/compliance/detail` ↔ `admin-compliance-detail.html`
- `admin/settlements/detail` ↔ `admin-settlement-detail.html`
- `admin/providers/detail` ↔ `admin-provider-detail.html`
- `admin/users/new` + `workorder/orders/new` + `risk-keywords/create+edit` ↔ 对应 form HTML
- `ops/providers/new` ↔ `ops-provider-new.html`

## v1.0 时期遗留差异（v1.6 候选还原项）

下列页面的 HTML 设计稿样式较 React 实现更精致/更具品牌感，建议在 v1.6 sprint 中逐一还原：

| 优先 | 页面 | HTML 设计要素 | 当前 React 现状 |
|---|---|---|---|
| 高 | `admin.html` 整体 app shell | 顶栏 + 侧栏 + 多 section 内嵌切换 | 已用 AppLayout + Sidebar + 路由分页（不同架构，但 token 一致） |
| 高 | `admin/cases` 看板 | 看板 column + 案件卡片优先级颜色 | React 已实现 kanban 视图，颜色/留白可微调 |
| 中 | `agent-pc.html` 多区域 | 左案件队列 + 中通话区 + 右脚本/AI | 已通过 RealtimeCallShell 实现，3 栏布局对齐 |
| 中 | `legal.html` / `workorder.html` 列表样式 | 表格 + 状态徽章风格 | React 列表 ok，部分 badge 颜色可对齐 |
| 低 | `platform-superadmin.html` 子页面 | 12 个 sub-section 各自精心设计 | React super 仅实现核心 4 页（health/audit/cost/plans），其他 sub-section 可作为 v2.x 候选 |

## 还原原则

1. **设计 token 优先于硬编码颜色**：使用 `var(--color-primary)`、`var(--color-success)` 等而非 `#1A56DB`、`#10b981`
2. **结构上对齐**：保持 HTML 的层级（headers / cards / sections）一致，便于设计师对照
3. **复用 lucide-react 图标**：HTML 用 `<i data-lucide="...">` 配合 CDN，React 用 `import { ... } from "lucide-react"`，图标名一致即可
4. **文案完全一致**：即便细微的「请输入手机号」vs「手机号 / 账号」差异也消除
5. **避免破坏功能**：还原时保留所有现有 hook、route、business logic，只改 JSX 视觉层

## 验收建议

- 浏览器同时打开 HTML 原型 + React 实际页面（两个 tab），目视对照
- Playwright 截图对比可作为 v1.7 自动化候选
- 设计师参与一轮 walkthrough 后再签收
