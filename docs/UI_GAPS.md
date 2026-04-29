# PRD-UI 缺口排查报告

> 生成日期：2026-04-29（最后更新：2026-04-29 新增角色 10/11 项目负责人）  
> PRD 版本：v0.7 + 项目负责人角色增补（`docs/PRD.md`）  
> 排查范围：PRD §21 全部 82 页，重点核对 P0 页  
> 说明：P1 占位页（带 `.p1-banner` 或"v1.1 功能"标记）属于有意延后，不计为缺口。

---

## 执行摘要

| 分类 | 数量 |
|------|------|
| ✅ P0 完整实现 | 64 |
| ⚠️ P0 部分缺失 | 8 |
| ❌ P0 完全缺失 | 1 |
| P1 stub（已标记，暂缓）| 20 |
| 非 MVP，v1.1 暂缓 | 2 |
| UI 超出 PRD §21 的额外页 | 7 |
| **PRD §21 总页数** | **82** |

> **2026-04-29 新增**：项目负责人角色（两侧共用模板）新增 4 个 P0 页（10.1–10.4 均已落 UI `project-manager.html`）+ 物业管理员新增项目管理页（`a-projects`，含 3 个 modal）+ 服务商管理员新增项目列表页（`pa-projects`，含 2 个 modal），共 +4 计入 ✅ 完整实现。

> **2026-04-29 范围变更**：支付二维码全屏（PRD 5A.6 / 6.5）产品决策调整为**非 MVP 功能**，从 P0 ❌ 移出，暂缓至 v1.1。

### 必须修复的 P0 缺口（阶段 B 优先处理）

| 序号 | UI 文件 | 缺失内容 | 来源 |
|------|---------|---------|------|
| ❌ 1 | `supervisor.html` | 升级案件处理（4.5）— 无专属 page-section | PRD §21 角色5 |
| ⚠️ 3 | `platform-superadmin.html` | 成本看板（通话分钟总量/成本汇总）— 产品决策未落 UI | 产品决策 Q1 |
| ⚠️ 4 | `platform-ops.html` | 租户配额配置（设置通话分钟配额）— 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 5 | `platform-ops.html` | ops-tenant-detail 缺"本月通话分钟"用量字段 | PRD §21 2.3 |
| ⚠️ 6 | `admin.html` | 物业公司分钟用量/配额视图 — 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 7 | `provider-admin.html` | 服务商分钟用量视图 — 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 8 | `supervisor.html` | 团队分钟用量趋势卡片 — 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 9 | `agent-pc.html` | 本人本月分钟数小卡 — 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 10 | `app-agent.html` | 本人本月分钟数 — 产品决策未落 UI | 产品决策 Q3 |
| ⚠️ 11 | `agent-pc.html` | 5B.2 案件详情页无独立 section；只有通话工作台内嵌 drawer | PRD §21 角色6B |

---

## 逐页核对表

### 角色 1：平台超管（`platform-superadmin.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| SA.1.1 | 系统健康监控 | P0 | `p-health` | ✅ | — |
| SA.1.2 | 平台运营员账号管理 | P0 | `p-ops-accounts` | ✅ | — |
| SA.1.3 | 套餐配置 | P0 | `p-packages` | ✅ | — |
| SA.1.4 | LLM基础Prompt管理 | P1 | `p-prompt` | ✅ P1 stub | — |
| SA.1.5 | 全局风控关键词 | P0 | `p-keywords` | ✅ | — |
| SA.1.6 | App版本管理 | P0 | `p-app-version` | ✅ | — |
| SA.1.7 | 区块链存证配置 | P1 | `p-blockchain` | ✅ P1 stub | — |
| SA.1.8 | 平台审计日志 | P0 | `p-audit` | ✅ | — |
| SA.1.9 | 数据库与存储管理 | P1 | `p-storage` | ✅ P1 stub | — |
| SA.★ | **成本看板（通话分钟池总量/成本汇总）** | **P0** | — | ⚠️ **缺失** | 产品决策Q1：超管应可查全平台分钟消耗与费用；无对应 page-section |

**修复建议**：在 `platform-superadmin.html` 新增 `p-cost-dashboard` page-section，展示：全平台分钟池总量/已用/剩余、各租户费用排名、本月成本趋势图。

---

### 角色 2：平台运营员（`platform-ops.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| OPS.2.1 | 运营数据大盘 | P0 | `ops-dashboard` | ✅ | — |
| OPS.2.2 | 租户列表 | P0 | `ops-tenants` | ✅ | — |
| OPS.2.3 | 租户详情 | P0 | `ops-tenant-detail` | ⚠️ | PRD 2.3 要求"当前用量（用户数/案件数/本月通话分钟）"；UI 当前只显示"本月存储用量"，缺**本月通话分钟** |
| OPS.2.4 | 开通新租户 | P0 | `ops-new-tenant` | ✅ | — |
| OPS.2.5 | 租户续费/变更套餐 | P0 | `ops-tenant-renew` | ✅ | — |
| OPS.2.6 | 租户停用/恢复 | P0 | `ops-tenant-disable` | ✅ | — |
| OPS.2.7 | 试用账号跟进 | P0 | `ops-trial` | ✅ | — |
| OPS.2.8 | 服务商列表 | P0 | `ops-providers` | ✅ | — |
| OPS.2.9 | 服务商审核 | P0 | `ops-provider-audit` | ✅ | — |
| OPS.2.10 | 服务商详情 | P0 | `ops-provider-detail` | ✅ | — |
| OPS.2.11 | 全平台结算总览 | P1 | `ops-settlement` | ✅ P1 stub | — |
| OPS.2.12 | 客户跟进记录 | P1 | `ops-followup` | ✅ P1 stub | — |
| OPS.2.13 | 系统公告管理 | P1 | `ops-announcement` | ✅ P1 stub | — |
| OPS.2.14 | 运营员操作日志（本人）| P1 | `ops-my-log` | ✅ P1 stub | — |
| OPS.★ | **租户通话分钟配额配置** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：运营员应能设定各租户的通话分钟配额；无对应入口（可在 ops-tenant-detail 内新增，或新建独立 section） |

**修复建议**：
1. `ops-tenant-detail` 用量区块增加"本月通话分钟（已用 X / 配额 Y）"字段；
2. `ops-tenant-renew` 或 `ops-tenant-detail` 中增加"调整分钟配额"操作按钮，跳转配额配置 modal。

---

### 角色 3：服务商管理员（`provider-admin.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| PA.3.1 | 服务商概览 | P0 | `pa-overview` | ✅ | — |
| PA.3.2 | 团队成员管理 | P0 | `pa-members` | ✅ | — |
| PA.3.3 | 合约管理 | P0 | `pa-contracts` | ✅ | — |
| PA.3.4 | 应收账款 | P0 | `pa-receivables` | ✅ | — |
| PA.3.5 | 成员绩效汇总 | P1 | `pa-performance` | ✅ P1 stub | — |
| PA.3.6 | 成员个人佣金 | P1 | `pa-commission` | ✅ P1 stub | — |
| PA.3.7 | 结算异议提交 | P1 | `pa-dispute` | ✅ P1 stub | — |
| PA.★ | **本服务商通话分钟用量** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：pa-overview 应展示本服务商的通话分钟消耗量；当前无此数据区块 |

**修复建议**：`pa-overview` 的 KPI 区块增加"本月通话分钟（已用）"指标卡。

---

### 角色 4：物业公司管理员（`admin.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| ADM.3.1 | 管理看板首页 | P0 | `a-dashboard` | ✅ | — |
| ADM.3.2 | CRM案件列表 | P0 | `a-cases` | ✅ | — |
| ADM.3.3 | CRM案件看板 | P0 | `a-kanban` | ✅ | — |
| ADM.3.4 | 案件详情页 | P0 | `a-case-detail` | ✅ | — |
| ADM.3.5 | 公海管理 | P0 | `a-pool` | ✅ | — |
| ADM.3.6 | 业主名单导入 | P0 | `a-import` | ✅ | — |
| ADM.3.7 | 录音批量上传 | P0 | `a-batch` | ✅ | — |
| ADM.3.8 | 用户管理 | P0 | `a-users` | ✅ | — |
| ADM.3.9 | 服务商合作管理 | P1 | `a-partners` | ✅ P1 stub | — |
| ADM.3.10 | 结算管理 | P0 | `a-settlement` | ✅ | — |
| ADM.3.11 | 话术库管理 | P1 | `a-scripts` | ✅ P1 stub | — |
| ADM.3.12 | 数据报表 | P1 | `a-reports` | ✅ P1 stub | — |
| ADM.3.13 | 合规月报 | P1 | `a-compliance` | ✅ P1 stub | — |
| ADM.3.14 | 系统配置 | P1 | `a-settings` | ✅（已实现，超出P0范围）| — |
| ADM.★ | **本物业公司分钟用量/配额视图** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：管理员应能看到本公司本月分钟已用/剩余配额；无对应区块（可在 a-dashboard 增加指标卡） |

**修复建议**：`a-dashboard` KPI 区块增加"本月通话分钟（已用 X / 配额 Y，剩余 Z）"指标卡；若剩余不足 20% 则以橙色警示。

---

### 角色 5：主管/督导（`supervisor.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| SV.4.1 | 督导工作台首页 | P0 | `sv-workspace` | ✅ | — |
| SV.4.2 | CRM案件列表（本组）| P0 | `sv-cases` | ✅ | — |
| SV.4.3 | 案件详情页 | P0 | — | ⚠️ | PRD说"同管理员但只看本组"；无独立 nav item，可从 sv-cases 行跳转 modal，但无显式 page-section；建议与 SV.4.5 一并补充 |
| SV.4.4 | 质检复核工作台 | P0 | `sv-review` | ✅ | — |
| SV.4.5 | 升级案件处理 | P0 | — | ❌ **完全缺失** | 无专属页面。PRD要求：升级案件队列、查看全部历史通话摘要、记录协商进展（分期协议）、可再次升级法务 |
| SV.4.6 | 风控事件记录 | P1 | `sv-risk` | ✅（已实现，超出P0）| — |
| SV.4.7 | 团队绩效 | P1 | `sv-stats` | ✅ P1 stub | — |
| SV.★ | **团队通话分钟用量趋势** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：sv-workspace 或单独区块展示本组本月分钟消耗趋势 |

> **注**：UI 额外实现了 `sv-team`（团队监控实时看板）和 `sv-scripts`（话术反馈）两个页面，不在 PRD §21 中，属于有益扩展，无需删除。

**修复建议**：
1. 新增 `sv-escalated` page-section：升级案件列表（大额/疑难，来自催收员升级）+ 协商进展记录 + 再次升级法务按钮；
2. `sv-workspace` 增加本月分钟用量趋势卡片。

---

### 角色 6A：内部催收员 App（`app-agent.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| AGA.5A.1 | 今日任务列表（首页）| P0 | `app-home` | ✅ | — |
| AGA.5A.2 | 公海浏览 | P0 | `app-cases` | ✅ | — |
| AGA.5A.3 | 拨号前业主预览 | P1 | `app-case-detail` | ✅ P1 | — |
| AGA.5A.4 | 实时通话界面 | P0 | `app-in-call` | ✅ | — |
| AGA.5A.5 | 通话后标记弹窗 | P0 | `app-after-call` | ✅ | — |
| AGA.5A.6 | **支付二维码全屏** | **P0** | — | ❌ **完全缺失** | 业主专属大图二维码屏幕整体缺失；通话中无任何"发支付二维码"按钮或全屏展示逻辑 |
| AGA.5A.7 | 今日绩效小结 | P1 | — | ⚠️ P1 | `app-home` 有简单今日统计，但无独立绩效小结页；可接受（P1），或补至 app-profile |
| AGA.5A.8 | 个人设置 | P1 | `app-profile` | ✅ P1 | — |
| AGA.★ | **本人本月分钟数** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：app-home 或 app-profile 应展示本人本月通话分钟使用量 |

> **注**：UI 额外实现了 `app-dial-request`（PC触发拨打请求屏）、`app-call-history`（通话记录）、`app-force-logout`（强制退出），均合理，无需删除。

**修复建议**：
1. `app-in-call` 通话控制栏增加"💳 发支付码"浮动按钮，点击展示新全屏 `app-payment-qr` 页，显示业主专属大图二维码；
2. `app-home` 的今日摘要卡增加"本月通话 X 分钟"指标。

---

### 角色 6B：内部催收员 PC（`agent-pc.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| AGB.5B.1 | 我的案件列表 | P0 | `my-cases` | ✅ | — |
| AGB.5B.2 | 案件详情页 | P0 | — | ⚠️ | 无独立 page-section；通话工作台内有 `detail-drawer`（欠费详情+通话记录），但仅在通话中可见；非通话时无法从案件列表进入独立详情页。PRD 5B.2 要求独立详情（业主信息+活动时间线+操作按钮） |
| AGB.5B.3 | 实时通话工作台（自动弹出）| P0 | `workstation` | ✅ | — |
| AGB.5B.4 | 个人绩效 | P1 | `my-profile` | ✅（含本月绩效摘要）| — |
| AGB.★ | **本人本月分钟数小卡** | **P0** | — | ⚠️ **缺失** | 产品决策Q3：my-profile 或 my-cases 侧边应展示本人本月通话分钟 |

> **注**：UI 额外实现了 `call-history`（通话记录），在 PRD §21 无对应页，属合理扩展。

**修复建议**：
1. `my-cases` 或 `my-profile` 新增案件详情侧滑面板（或独立 section），展示业主信息+欠费明细+活动时间线（仅本人操作）+ 操作按钮（建工单/转主管/转法务）；
2. `my-profile` 绩效摘要区增加"本月通话分钟"指标。

---

### 角色 7：外部兼职催收员（`app-agent.html` 同文件，权限受限）

> 外部兼职与内部催收员共用同一个 App 原型文件，权限差异通过角色控制实现。

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| EXT.6.1 | 今日任务列表 | P0 | `app-home` | ✅ | — |
| EXT.6.2 | 公海浏览 | P0 | `app-cases` | ✅ | — |
| EXT.6.3 | 实时通话界面 | P0 | `app-in-call` | ✅ | — |
| EXT.6.4 | 通话后标记弹窗 | P0 | `app-after-call` | ✅ | — |
| EXT.6.5 | 支付二维码 | P0 | — | ❌ **完全缺失** | 同 AGA.5A.6 缺口，修复 app-agent.html 后一并解决 |
| EXT.6.6 | 个人设置 | P1 | `app-profile` | ✅ P1 | — |

---

### 角色 8：法务专员（`legal.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| LEG.7.1 | 法务案件队列 | P0 | `legal-list` | ✅ | — |
| LEG.7.2 | 法务案件详情 | P0 | `legal-detail` | ✅ | — |
| LEG.7.3 | 进展更新 | P0 | — | ✅（modal）| 以"更新诉讼进展"modal 实现（`modal-update-stage`），包含全部状态流转和备注字段；UX 可接受，无需单独 section |
| LEG.7.4 | 存证包下载 | P1 | — | ✅ P1 | legal-detail 内有"区块链存证"区块，标注 v1.1 功能 |
| LEG.7.5 | 文件管理 | P1 | `legal-docs` | ✅ P1 | — |

> **注**：UI 额外实现了 `legal-workorder`（工单关联）和 `legal-stats`（法务统计），不在 PRD §21 中，属合理扩展。

---

### 角色 9：工单处理员（`workorder.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| WO.8.1 | 工单列表 | P0 | `wo-list` | ✅ | — |
| WO.8.2 | 工单详情 | P0 | `wo-detail` | ✅ | — |
| WO.8.3 | 工单处理 | P0 | `wo-process` | ✅ | — |
| WO.8.4 | 历史工单查询 | P1 | `wo-history` | ✅ P1 | — |

工单处理员角色全部覆盖，无缺口。

---

## 缺口优先级汇总（阶段 B 修复顺序）

### 批次一：P0 ❌（完全缺失，最高优先）

| # | 文件 | 新增内容 | 修复工作量 |
|---|------|---------|-----------|
| 1 | `app-agent.html` | 新增 `app-payment-qr` 全屏页（大图二维码 + 金额 + 物业信息）+ app-in-call 增加"发支付码"浮动按钮 | 中（约 1-2h） |
| 2 | `supervisor.html` | 新增 `sv-escalated` page-section（升级案件列表 + 协商进展记录 + 再次升级法务入口）+ sidebar item | 中（约 2h） |

### 批次二：P0 ⚠️ 产品决策（通话分钟池化，跨 6 个文件）

| # | 文件 | 新增内容 |
|---|------|---------|
| 3 | `platform-superadmin.html` | 新增 `p-cost-dashboard` section（全平台分钟池总量、各租户费用排名、成本趋势图）+ sidebar item |
| 4 | `platform-ops.html` | `ops-tenant-detail` 用量区增加"本月通话分钟（已用/配额）"字段 + 配额调整 modal |
| 5 | `admin.html` | `a-dashboard` KPI 区增加"本月通话分钟（已用/配额/剩余）"指标卡 |
| 6 | `provider-admin.html` | `pa-overview` KPI 区增加"本月通话分钟（已用）"指标卡 |
| 7 | `supervisor.html` | `sv-workspace` 增加分钟用量趋势卡片（本组本月已用分钟 / 日趋势小图）|
| 8 | `agent-pc.html` | `my-profile` 增加"本月通话分钟"指标；`my-cases` 增加案件详情独立 section |
| 9 | `app-agent.html` | `app-home` 摘要卡增加"本月通话 X 分钟"（同批次1合并处理）|

### 批次三：P0 ⚠️ 功能完整性

| # | 文件 | 内容 |
|---|------|------|
| 10 | `agent-pc.html` | 5B.2 案件详情：`my-cases` 列表行增加"详情"按钮，打开独立侧滑面板或新 section，展示业主信息+欠费明细+活动时间线（仅本人）+操作按钮 |

---

## UI 中存在但 PRD §21 未列入的额外页面

> 这些页面属于有益扩展，无需删除，但也不进入验收清单（ACCEPTANCE.md 不对账）。

| 文件 | data-page | 页面名称 | 说明 |
|------|-----------|---------|------|
| `supervisor.html` | `sv-team` | 团队监控 | 实时通话状态看板，是 4.1 工作台的扩展视图 |
| `supervisor.html` | `sv-scripts` | 话术反馈 | 对 AI 推送话术评价，产品价值高，可正式纳入后续 PRD |
| `legal.html` | `legal-workorder` | 工单关联 | 法务案件关联工单，合理 |
| `legal.html` | `legal-stats` | 法务统计 | 法务案件统计，合理 |
| `agent-pc.html` | `call-history` | 通话记录 | 催收员自己的通话历史，合理 |
| `app-agent.html` | `app-dial-request` | PC触发拨打请求 | PC→App DIAL_REQUEST 弹窗逻辑，合理 |
| `app-agent.html` | `app-force-logout` | 强制退出 | 安全功能，合理 |

---

## 下一步

1. **阶段 B**：按上方"批次一 → 批次二 → 批次三"顺序补完 P0 缺口。
2. **目标状态**：所有 P0 行状态变为 ✅；P1 行保留 stub 标记不变。
3. **阶段 C**：基于已对齐的 UI 编写 CODING_STANDARDS.md / TESTING_STANDARDS.md / ACCEPTANCE.md（ACCEPTANCE.md 中的 DoD 将引用本表的 ✅ 状态）。
