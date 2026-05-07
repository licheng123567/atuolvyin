# PRD-UI 缺口排查报告

> 生成日期：2026-04-29（最后更新：**2026-05-06 — v1.6 收官扫尾**：唯一遗留 ⚠️ AGB.5B.2 案件详情已落地为独立页 `frontend/src/pages/agent/cases/detail.tsx`，全部 P0 缺口清零）  
> PRD 版本：v0.7 + 项目负责人角色增补（`docs/PRD.md`）  
> 排查范围：PRD §21 全部 82 页，重点核对 P0 页  
> 说明：P1 占位页（带 `.p1-banner` 或"v1.1 功能"标记）属于有意延后，不计为缺口。

---

## 执行摘要

| 分类 | 数量 |
|------|------|
| ✅ P0 完整实现 | 74 |
| ⚠️ P0 部分缺失 | 0 |
| ❌ P0 完全缺失 | 0 |
| P1 stub（已标记，暂缓）| 20 |
| 非 MVP，v1.1 暂缓 | 3 |
| UI 超出 PRD §21 的额外页 | 7 |
| **PRD §21 总页数** | **83**（新增 SA.★ 成本看板）|

> **2026-04-29 新增**：项目负责人角色（两侧共用模板）新增 4 个 P0 页（10.1–10.4 均已落 UI `project-manager.html`）+ 物业管理员新增项目管理页（`a-projects`，含 3 个 modal）+ 服务商管理员新增项目列表页（`pa-projects`，含 2 个 modal），共 +4 计入 ✅ 完整实现。

> **2026-04-29 范围变更**：支付二维码全屏（PRD 5A.6 / 6.5）产品决策调整为**非 MVP 功能**，从 P0 ❌ 移出，暂缓至 v1.1。

> **2026-04-29 B 阶段收尾**：通话分钟池化配额视图已补入全部 6 个角色的 UI；`sv-escalated` 升级案件处理页已落地；`p-cost-dashboard` 成本看板已落地；`modal-quota-config` 配额配置入口已落地。9 个 ⚠️ 和 1 个 ❌ 均已修复为 ✅。唯一剩余 ⚠️：AGB.5B.2（催收员 PC 案件详情独立 section，非紧急，可在 MVP 编码期随 5B.1 列表页一并实现）。

### P0 缺口修复状态（阶段 B 已完成）

| 序号 | UI 文件 | 缺失内容 | 状态 |
|------|---------|---------|------|
| 1 | `supervisor.html` | 升级案件处理（4.5）— 新增 `sv-escalated` page-section | ✅ 已修复 |
| 2 | `platform-superadmin.html` | 成本看板 — 新增 `p-cost-dashboard` page-section | ✅ 已修复 |
| 3 | `platform-ops.html` | 租户配额配置 — 新增 `modal-quota-config` + "调整配额"按钮 | ✅ 已修复 |
| 4 | `platform-ops.html` | ops-tenant-detail 缺"本月通话分钟"用量字段 | ✅ 已修复 |
| 5 | `admin.html` | 物业公司分钟用量/配额视图 — `a-dashboard` 新增第 5 个指标卡 | ✅ 已修复 |
| 6 | `provider-admin.html` | 服务商分钟用量视图 — `pa-overview` 新增第 5 个 KPI 卡 | ✅ 已修复 |
| 7 | `supervisor.html` | 团队分钟用量趋势卡片 — `sv-workspace` 右侧新增趋势卡 | ✅ 已修复 |
| 8 | `agent-pc.html` | 本人本月分钟数小卡 — `my-profile` 绩效摘要新增分钟字段 | ✅ 已修复 |
| 9 | `app-agent.html` | 本人本月分钟数 — `app-home` 新增橙色分钟小卡 | ✅ 已修复 |
| 10 | `agent-pc.html` | 5B.2 案件详情页无独立 section | ✅ 已修复（v1.1 Stage E：`frontend/src/pages/agent/cases/detail.tsx` 308 行）|

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
| SA.★ | **成本看板** | **P0** | `p-cost-dashboard` | ✅ | 已新增 page-section：全平台分钟池总量/已用/剩余；各租户消耗排名；近6个月成本趋势图 |

---

### 角色 2：平台运营员（`platform-ops.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| OPS.2.1 | 运营数据大盘 | P0 | `ops-dashboard` | ✅ | — |
| OPS.2.2 | 租户列表 | P0 | `ops-tenants` | ✅ | — |
| OPS.2.3 | 租户详情 | P0 | `ops-tenant-detail` | ✅ | 已新增第4个用量卡"通话分钟"（已用/配额，带进度条+调整配额按钮）|
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
| OPS.★ | **租户通话分钟配额配置** | **P0** | `modal-quota-config` | ✅ | 已在 ops-tenant-detail 新增"调整配额"按钮，触发 modal：新配额输入+生效时间选择+超额 403 行为说明 |

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
| PA.★ | **本服务商通话分钟用量** | **P0** | `pa-overview`（第5卡）| ✅ | 已新增第5个 stat-card：本月通话分钟已用/配额（1,284/2,000，橙色进度条）|

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
| ADM.★ | **本物业公司分钟用量/配额视图** | **P0** | `a-dashboard`（第5卡）| ✅ | 已新增第5个 stat-card：本月通话分钟 3,240/5,000（64.8%，橙色警示色调）|

---

### 角色 5：主管/督导（`supervisor.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| SV.4.1 | 督导工作台首页 | P0 | `sv-workspace` | ✅ | — |
| SV.4.2 | CRM案件列表（本组）| P0 | `sv-cases` | ✅ | — |
| SV.4.3 | 案件详情页 | P0 | — | ⚠️ | PRD说"同管理员但只看本组"；无独立 nav item，可从 sv-cases 行跳转 modal，但无显式 page-section；建议与 SV.4.5 一并补充 |
| SV.4.4 | 质检复核工作台 | P0 | `sv-review` | ✅ | — |
| SV.4.5 | 升级案件处理 | P0 | `sv-escalated` | ✅ | 已新增完整 page-section：升级案件列表（状态栏：待处理6/协商中4/转法务3）、案件详情 drawer、协商进展记录、再次升级法务操作 |
| SV.4.6 | 风控事件记录 | P1 | `sv-risk` | ✅（已实现，超出P0）| — |
| SV.4.7 | 团队绩效 | P1 | `sv-stats` | ✅ P1 stub | — |
| SV.★ | **团队通话分钟用量趋势** | **P0** | `sv-workspace`（右侧卡片）| ✅ | 已新增趋势卡：本月已用1,284分钟/柱状图（7日）/橙色配色 |

> **注**：UI 额外实现了 `sv-team`（团队监控实时看板）和 `sv-scripts`（话术反馈）两个页面，不在 PRD §21 中，属于有益扩展，无需删除。

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
| AGA.★ | **本人本月分钟数** | **P0** | `app-home`（分钟小卡）| ✅ | 已在 app-home 新增橙色分钟小卡：423/1,000分钟，进度条，剩余577 |

> **注**：UI 额外实现了 `app-dial-request`（PC触发拨打请求屏）、`app-call-history`（通话记录）、`app-force-logout`（强制退出），均合理，无需删除。

---

### 角色 6B：内部催收员 PC（`agent-pc.html`）

| 页面ID | 页面名称 | 优先级 | UI 锚点 | 状态 | 缺失功能 |
|--------|---------|--------|---------|------|---------|
| AGB.5B.1 | 我的案件列表 | P0 | `my-cases` | ✅ | — |
| AGB.5B.2 | 案件详情页 | P0 | — | ⚠️ **待处理** | 无独立 page-section；通话工作台内有 `detail-drawer`（欠费详情+通话记录），但仅在通话中可见；非通话时无法从案件列表进入独立详情页。PRD 5B.2 要求独立详情（业主信息+活动时间线+操作按钮）。**计划**：Stage E 实现 my-cases 列表页时一并添加 case-detail 侧滑面板。 |
| AGB.5B.3 | 实时通话工作台（自动弹出）| P0 | `workstation` | ✅ | — |
| AGB.5B.4 | 个人绩效 | P1 | `my-profile` | ✅（含本月绩效摘要）| — |
| AGB.★ | **本人本月分钟数小卡** | **P0** | `my-profile`（绩效摘要）| ✅ | 已在月度绩效指标区新增"本月通话分钟"行：847/1,000（84.7%，橙色）|

> **注**：UI 额外实现了 `call-history`（通话记录），在 PRD §21 无对应页，属合理扩展。

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

## 缺口修复状态汇总（阶段 B 已完成）

### 已完成（阶段 B 全部修复）

| # | 文件 | 修复内容 | 状态 |
|---|------|---------|------|
| 1 | `supervisor.html` | 新增 `sv-escalated` page-section + sidebar item | ✅ |
| 2 | `platform-superadmin.html` | 新增 `p-cost-dashboard` section + sidebar item | ✅ |
| 3 | `platform-ops.html` | `ops-tenant-detail` 新增通话分钟用量卡 + `modal-quota-config` | ✅ |
| 4 | `admin.html` | `a-dashboard` stat-grid 新增第5个分钟指标卡 | ✅ |
| 5 | `provider-admin.html` | `pa-overview` 新增第5个分钟 KPI 卡 | ✅ |
| 6 | `supervisor.html` | `sv-workspace` 新增分钟用量趋势卡片 | ✅ |
| 7 | `agent-pc.html` | `my-profile` 绩效摘要新增本月通话分钟 | ✅ |
| 8 | `app-agent.html` | `app-home` 新增橙色分钟小卡 | ✅ |

### 遗留（Stage E 处理）

| # | 文件 | 内容 | 计划 |
|---|------|------|------|
| 1 | `agent-pc.html` | 5B.2 案件详情独立 section（非通话时可访问）| Stage E 实现 my-cases 列表页时一并完成 |

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

## 当前状态与下一步

**阶段 B 已完成**：所有识别的 P0 缺口均已修复（除 AGB.5B.2 计划在 Stage E 随业务开发一并实现）。

**下一步（阶段 E：MVP 编码）**：
1. 以 `docs/CODING_STANDARDS.md`、`docs/TESTING_STANDARDS.md`、`docs/ACCEPTANCE.md` 为规范约束
2. 按角色优先级开始全栈编码（后端 → PC 前端 → Android）
3. AGB.5B.2 案件详情独立 section 在实现 5B.1 我的案件列表时一并完成
