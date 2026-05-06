# UI 原型 vs React 实现 Gap 报告

**生成日期**：2026-05-06（v1.3 完成后）
**范围**：`ui/*.html` HTML 原型 vs `frontend/src/pages/**/*.tsx` 实际页面
**目的**：反向出原型时优先级排序的依据

## 总览

- **PC 原型 sections** ≈ 64 个（按各 HTML 内 page-section ID 计）
- **App 原型 sections** = 9 个（app-agent.html 内）
- **React 页面** = 71 个（不含 *.test.tsx）
- **大致覆盖率**：60% PC 页面有原型对照 / 40% 缺原型或缺反向

## A. 已对照覆盖（HTML 原型 ↔ React 页面）

### admin (admin.html — 14 sections)

| 原型 section | React 页面 |
|---|---|
| a-dashboard | admin/dashboard |
| a-cases | admin/cases |
| a-kanban | admin/cases/kanban |
| a-case-detail | admin/cases/detail |
| a-pool | admin/pool |
| a-import | admin/cases/import |
| a-users | admin/users |
| a-partners | admin/providers |
| a-reports | admin/reports |
| a-compliance | admin/compliance |
| a-settlement | admin/settlements |
| a-scripts | admin/scripts/list |
| a-settings | admin/settings |

**❌ 原型有 React 缺**：a-batch（批量分配视图）、a-projects（项目管理视图）

### legal (legal.html — 5 sections)

| 原型 | React |
|---|---|
| legal-list | legal/cases |
| legal-detail | legal/cases/[id] |
| legal-docs | legal/cases/[id] 内嵌 LegalDocumentsPanel |

**❌ 原型有 React 缺**：legal-workorder（法务工单视图）、legal-stats（法务统计）

### platform-ops (platform-ops.html — 14 sections)

| 原型 | React |
|---|---|
| ops-tenants / ops-tenant-detail / ops-new-tenant / ops-trial | ops/tenants/* |
| ops-providers / ops-provider-detail | ops/providers/* |
| ops-settlement | ops/settlements |
| ops-followup | ops/customer-followups |
| ops-announcement | ops/announcements |
| ops-my-log | ops/audit-logs |

**❌ 原型有 React 缺**：ops-dashboard（运营员总览）、ops-tenant-renew（续约 modal，可在 [id] 内做）、ops-tenant-disable（停用 modal）、ops-provider-audit（审核流，可在 [id] 内做）

### platform-superadmin (platform-superadmin.html — 10 sections)

| 原型 | React |
|---|---|
| p-health | super/health |
| p-packages | super/plans |
| p-prompt | super/llm-prompts |
| p-keywords | admin/risk-keywords/list |
| p-blockchain | super/blockchain-config |
| p-audit | super/audit |
| p-cost-dashboard | super/cost |

**❌ 原型有 React 缺**：p-ops-accounts（平台运营员账号管理）、p-app-version（App 版本配置）、p-storage（OSS 存储凭证管理 — 但这违反 PRD §3.14「存储凭证只在 .env」，建议**移除原型**）

### supervisor (supervisor.html — 8 sections)

| 原型 | React |
|---|---|
| sv-workspace | supervisor/alerts |
| sv-review | supervisor/reviews |
| sv-team | supervisor/team-performance |
| sv-scripts | supervisor/script-labels |
| sv-risk | supervisor/risk-events |

**❌ 原型有 React 缺**：sv-cases（督导案件视图）、sv-escalated（升级案件）、sv-stats（数据统计）

### workorder (workorder.html — 4 sections)

| 原型 | React |
|---|---|
| wo-list | workorder/orders |
| wo-detail | workorder/orders/[id] |
| wo-process | workorder/orders/[id] 内嵌 |

**❌ 原型有 React 缺**：wo-history（历史工单）

### provider-admin (provider-admin.html — 11 sections)

| 原型 | React |
|---|---|
| pa-overview | provider/dashboard |
| pa-members | provider/team |
| pa-receivables | provider/settlements |
| pa-performance | provider/team-performance |
| pa-commission | provider/commission |
| pa-dispute | provider/settlements/[id] DisputeSubmitButton |

**❌ 原型有 React 缺**：pa-projects（项目管理）、pa-contracts（合作合同）

### project-manager (project-manager.html — 4 sections)

| 原型 | React |
|---|---|
| pm-overview | pm/dashboard |

**❌ 原型有 React 缺**：pm-cases、pm-workorders、pm-legal

### app-agent (app-agent.html — Android — 9 sections)

| 原型 | Kotlin Activity |
|---|---|
| app-home | MainActivity |
| app-cases | CaseAdapter (in MainActivity) |
| app-case-detail | （未实现 — Sprint 11.1 仅做了拨号前预览 dialog，没独立详情页）|
| app-dial-request | （MiPush DIAL_REQUEST 收到后弹出，已实现）|
| app-in-call | RealtimeCallActivity |
| app-after-call | dialog_post_call_tag.xml |
| app-call-history | （未实现）|
| app-profile | SettingsActivity |
| app-force-logout | （未实现 — 等 Sprint 15.1 多设备踢出）|

## B. React 有但**完全没原型**（需反向出原型，按重要性排）

### P0（hero feature 或新功能必须有原型）

| React 页 | 备注 |
|---|---|
| ~~supervisor/live-wall~~ | ✅ Sprint 15.4 反向出原型，作为 supervisor.html 子 section（sv-livewall） |
| **agent/workstation/live** | 实时通话 PC 主控页，无原型 |
| **admin/workstation/live** | 实时通话 PC 管理员视图，无原型 |
| **calls/detail** | 通话详情页（录音回放/转写/AI/风控时间线）|

### P1（v1.1 / v1.2 / v1.3 新增页面）

| React 页 | 来源 sprint |
|---|---|
| supervisor/reviews/detail | Sprint 12.2 督导复核详情 |
| supervisor/risk-events | Sprint 9.4 风控事件记录 |
| admin/scripts/effectiveness | Sprint 8.2 话术效果看板 |
| admin/scripts/versions | 话术版本管理 |
| admin/compliance/detail | Sprint 8.4 合规月报详情 |
| admin/settlements/detail | 结算详情 |
| admin/providers/detail | Sprint 8.1 服务商合作详情 |
| admin/users/new | 新建用户 |
| **help/app** | v1.3 公开 App 下载页 |
| **verify (/:tx_hash)** | v1.2 公开核验入口 |
| workorder/orders/new | 新建工单 |
| risk-keywords/create + edit | 风控关键词管理 |

### P2（次要 / 服务商内部 / 平台超管细节）

| React 页 |
|---|
| provider/settlements + provider/settlements/[id] |
| provider/tenants |
| ops/providers/new |
| ops/tenants/new |
| ops/tenants/[id] |
| ops/tenants/trial |
| super/audit |
| super/cost |
| super/plans |

## C. 优先级总结（执行顺序）

**第一批（v1.3 hero + 公开页 5 个）**：
1. ~~supervisor/live-wall~~ ✅ 已落（supervisor.html#sv-livewall, Sprint 15.4）
2. help/app
3. verify
4. agent/workstation/live
5. admin/workstation/live

**第二批（缺失功能页 3 个 — 待 v1.4 实施时同步出原型）**：
6. p-ops-accounts（v1.4 多设备踢出沿带）
7. app-force-logout（v1.4 多设备踢出沿带）
8. legal-workorder + legal-stats

**第三批（每 sprint 顺手 1-2 个补完 P1/P2）**

## D. 已知问题 / 不一致

- 原型中 a-projects / pm-* / pa-projects 体现的「项目」概念在 React 中只在 admin/dashboard 内通过 PRD §6 "项目负责人" 间接体现，没有独立 CRUD 页面。需要 PRD 决策：项目管理是否独立模块，还是作为 case 的归属字段。
- 原型 p-storage（存储配置）违反 PRD §3.14「凭证只在 .env」，建议移除原型而非反向。
