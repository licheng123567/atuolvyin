# 服务商督导工作台 设计文档

> 状态：设计已与用户确认（2026-05-17），待用户复审本文档后转实施计划。

## 背景与目标

服务商督导（`role=supervisor` + `UserTenantMembership.provider_id` 非 NULL）当前无专属工作流：掉进物业督导 nav，而 `/supervisor/*` 端点全部只按 `tenant_id` 过滤（隐含物业侧），导致服务商督导大面积 403、数据全空。2026-05-17 已临时把其 nav 裁窄为只剩帮助中心止血。

**目标**：把服务商督导「做实」—— 让其能监管本服务商的催收员与案件，功能范围与物业督导对等但数据 scope 到本服务商。

## 范围（产品已确认）

服务商督导需要 10 项功能。本设计分两期：

**Phase 1（9 项，纯查询 scope-aware 改造，不动 schema）**：督导工作台、实时通话墙、团队监控、质检复核、话术反馈、风控事件、我的 KPI、团队报表、公海管理。

**Phase 2（1 项，需数据模型迁移）**：值班排班。

**不在范围**：减免审批、法务转化审批（物业侧权责）；升级案件处理、承诺催付、案件超期报警、培训案例库（本轮产品未纳入）。

## 架构

### 核心模式：scope-aware 查询

12 个 `/supervisor/*` 端点的查询从「只按 tenant」改为「按 scope 分流」：
- **物业督导**（scope=`tenant:{id}`，`provider_id IS NULL`）：查 `Project.provider_id IS NULL` 的案件 / 物业侧催收员。
- **服务商督导**（scope=`provider:{id}`）：查 `Project.provider_id = 本服务商` 的案件 / 本服务商催收员。

### 复用既有 provider scope-aware 范例

`app/api/provider_legal.py` 已有成熟范例，本设计复用并泛化：
- `_ctx(payload) -> (tenant_id, provider_id, user_id)` —— 从 token 解析三元组。
- `_provider_legal_case_filter(tenant_id, provider_id)` —— 案件按 provider 名下活跃项目过滤。

**新增共享件**（建议放 `app/api/_supervisor_scope.py` 或复用 `provider_legal` 的）：
- `supervisor_scope(payload) -> SupervisorScope` —— 解析督导是物业侧还是服务商侧，返回 `provider_id`（物业侧为 `None`）。
- `supervisor_case_filter(tenant_id, provider_id_or_none)` —— `provider_id` 为 `None` 时过滤 `Project.provider_id IS NULL`，否则过滤 `Project.provider_id == provider_id`。物业/服务商两侧共用一个 filter。
- `supervisor_agent_filter(tenant_id, provider_id_or_none)` —— 团队成员过滤：服务商侧 `UserTenantMembership(provider_id=X, role='agent')`，物业侧 `provider_id IS NULL`。

### 守卫

`/supervisor/*` 端点守卫从 `require_tenant_roles(supervisor, ...)`（断言 `provider_id IS NULL`）改为 `require_roles(supervisor, ...)`（跨两侧），端点内用 `supervisor_scope()` 分流。凡涉及 `agent` 角色的端点本就该用 `require_roles`（见 CLAUDE.md 多租户规则）。

### 数据归属规则（调研已确认）

| 概念 | 物业督导 | 服务商督导 |
|------|---------|-----------|
| 团队（催收员） | `UserTenantMembership(role='agent', provider_id IS NULL)` | `UserTenantMembership(role='agent', provider_id=本服务商)` |
| 公海/案件 | `CollectionCase` → `Project.provider_id IS NULL` 的 public 案件 | `CollectionCase` → `Project.provider_id=本服务商` 的 public 案件（无独立公海表） |
| 通话/质检/风控数据 | `CallRecord`/`RiskEvent`/`AnalysisResult`/`SuggestionFeedback` 无直接 `provider_id`，经 `call_id → CallRecord.case_id → CollectionCase.project_id → Project.provider_id` 链过滤 |

## Phase 1 — 端点改造清单

| 功能 | 端点 | 文件:行 | 改造 |
|------|------|--------|------|
| 公海管理 | `GET /supervisor/cases` | supervisor.py:24 | 加 `supervisor_case_filter`；案件动作端点同步 |
| 实时通话墙 | `GET /supervisor/live-calls` | supervisor_live.py:62 | 加 case→project→provider 过滤 |
| 实时通话墙 | `WS /ws/supervisor` | ws_supervisor.py:26 | 推送按 provider scope 过滤 |
| 实时通话墙 | `POST /supervisor/calls/{id}/force-hangup`、`/takeover` | supervisor_live.py:123/174 | 加 provider 权限校验 |
| 质检复核 | `GET /supervisor/reviews`、`GET/PATCH /supervisor/reviews/{call_id}` | supervisor_review.py:77/124 | 加 call→case→project→provider 过滤 |
| 话术反馈 | `GET /supervisor/script-labels`、`POST /supervisor/script-labels/{id}` | supervisor_labels.py:22 | 加 call→case→project→provider 过滤 |
| 风控事件 | `GET /supervisor/risk-events`、`PATCH /supervisor/risk-events/{id}` | supervisor_extras.py:51/93 | 加 call→case→project→provider 过滤 |
| 团队监控 | `GET /supervisor/team-performance` | supervisor_extras.py:146 | 团队列表用 `supervisor_agent_filter`；call/case 加 provider scope（🔴 较重） |
| 我的 KPI / 团队报表 | `GET /supervisor/team-stats` | supervisor_team_stats.py:33 | 同上，agent 聚合用 `supervisor_agent_filter`（🔴 较重） |
| 督导工作台 | 聚合多端点 | supervisor/workspace | 依赖上述端点改造完即生效 |

每个端点改造后**必须**配多租户隔离测试。

## Phase 2 — 值班排班

`SupervisorShift` 表用 `supervisor_name`（文本）标识、无 provider 维度。改造：
1. Alembic 迁移：`SupervisorShift` 加 `supervisor_user_id`（FK→user_account）、`provider_id`（可空）列；回填既有行（按 `supervisor_name` 反查）。
2. `GET/POST /supervisor/shifts`、`swap-request` 等端点按 `provider_id` scope。
3. 排班督导下拉用 `supervisor_agent_filter` 同源逻辑过滤本服务商督导。

Phase 2 独立成实施计划，Phase 1 完成并验收后启动。

## 前端

- `frontend/src/config/nav.ts`：把 `getNavSections` 里 `supervisor + provider:` 分支现在返回的 `[HELP_SECTION]` 占位，替换为真正的 `SUPERVISOR_PROVIDER_NAV`（Phase 1 的 9 项；Phase 2 上线后加排班）。
- 督导页面组件基本 scope-agnostic（调端点、渲染）—— 端点改 scope-aware 后多数直接复用，前端改动集中在 nav。个别页面（团队监控/报表）若有「物业」字样文案需按服务商口径微调。

## 测试

- **多租户隔离（铁律）**：每个改造端点配测试 —— 服务商 A 的督导查不到服务商 B 的数据、查不到物业侧数据；物业督导查不到任何服务商数据。
- 用 testcontainers，自建 fixture，不依赖 seed_demo。
- per-role E2E：把服务商督导账号 `13000000013`... （注：`13000000013` 是服务商法务；服务商督导是 `13000000012`）`13000000012` 的关键页接进 `per-role-pages.spec.ts`。

## 错误处理

- 端点错误响应沿用项目扁平 `{code, message}`。
- `supervisor_scope()` 解析不到合法 scope → `403 ERR_NO_SCOPE`，参照 `provider_legal._ctx` 的 `ERR_NO_TENANT` 写法。

## 风险

- `team-performance` / `team-stats` 的 agent 聚合涉及多表 join，是改造最重的两处 —— 实施计划里单独拆任务、重点测试。
- WS `/ws/supervisor` 的 scope 过滤需与 HTTP 端点口径一致，避免实时推送泄漏跨 provider 数据。

---

> ✅ **Phase 1 已实现（2026-05-18）**：9 项 `/supervisor/*` 端点（公海/案件、实时通话墙 3 端点、`WS /ws/supervisor`、质检复核 3 端点、话术反馈、风控 2 端点、团队监控、团队报表/KPI）全部 scope-aware，配 `app/api/_supervisor_scope.py` 共享件（`supervisor_scope` / `supervisor_case_filter` / `supervisor_call_filter` / `supervisor_agent_filter` / `resolve_call_provider_id`）；前端 `SUPERVISOR_PROVIDER_NAV`（9 项）已接入 `getNavSections`。每端点配多租户三向隔离测试，后端全量回归 834 passed。详见实施计划 `docs/superpowers/plans/2026-05-17-provider-supervisor-workspace.md`。
>
> ⬜ **Phase 2（值班排班）待启动** —— 需 `SupervisorShift` 表迁移（加 `supervisor_user_id` / `provider_id` 列），独立成实施计划。
