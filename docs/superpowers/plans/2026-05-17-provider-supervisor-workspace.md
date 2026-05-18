# 服务商督导工作台 Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把服务商督导（`role=supervisor` + `provider_id` 非 NULL）做实 —— 9 项日常功能的 `/supervisor/*` 端点改 scope-aware，服务商督导只看本服务商数据。

**Architecture:** 抄 `provider_legal.py` 的 scope-aware 范例，新建共享 helper（`supervisor_scope` / `supervisor_case_filter` / `supervisor_agent_filter`），逐端点把「只按 tenant 过滤」改成「按 scope 分流」。守卫从 `require_tenant_roles` 换 `require_roles`。前端把 nav 占位换成真 nav。每端点配多租户隔离测试。

**Tech Stack:** FastAPI + SQLAlchemy（后端）；React + TypeScript（前端 nav）；pytest + testcontainers / Vitest / Playwright（测试）。

设计依据：`docs/superpowers/specs/2026-05-17-provider-supervisor-workspace-design.md`。

---

## Task 1: 共享 scope helper

**Files:**
- Create: `poc/backend/app/api/_supervisor_scope.py`
- Test: `poc/backend/tests/api/test_supervisor_scope.py`

- [ ] **Step 1: 写失败测试** — `test_supervisor_scope.py`：建物业项目案件 + 服务商项目案件 + 无项目案件，断言 `supervisor_case_filter`：物业 scope 命中「无项目 + 物业项目」案件、不命中服务商项目案件；服务商 scope 只命中本服务商项目案件。`supervisor_agent_filter`：物业 scope 命中 `provider_id IS NULL` 的 agent，服务商 scope 命中本服务商 agent。沿用 `tests/api/` 既有 fixture 风格（`db_session`、`seeded_tenant`），不依赖 seed_demo。

- [ ] **Step 2: 跑测试确认失败** — `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_scope.py -q`，Expected: FAIL（模块不存在）。

- [ ] **Step 3: 创建 `_supervisor_scope.py`**：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from app.core.security import get_token_payload
from app.models.case import CollectionCase, Project
from app.models.tenant import UserTenantMembership


@dataclass(frozen=True)
class SupervisorScope:
    tenant_id: int
    provider_id: int | None  # None=物业侧督导；非 None=服务商侧督导


def supervisor_scope(payload: Annotated[dict, Depends(get_token_payload)]) -> SupervisorScope:
    """从 token 解析督导 scope。可作 FastAPI 依赖直接注入。"""
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_SCOPE", "message": "需要租户上下文"},
        )
    provider_id = payload.get("provider_id")
    return SupervisorScope(
        tenant_id=int(tenant_id),
        provider_id=int(provider_id) if provider_id else None,
    )


def _provider_projects(scope: SupervisorScope):
    """子查询：本 scope 下的项目 id 集。"""
    q = select(Project.id).where(Project.tenant_id == scope.tenant_id)
    if scope.provider_id is None:
        return q.where(Project.provider_id.is_(None))
    return q.where(Project.provider_id == scope.provider_id)


def supervisor_case_filter(scope: SupervisorScope):
    """案件可见性。物业督导：无项目案件 + 物业项目案件；服务商督导：仅本服务商项目案件。"""
    if scope.provider_id is None:
        # 物业侧：排除「归属某服务商项目」的案件
        provider_project_ids = select(Project.id).where(
            Project.tenant_id == scope.tenant_id,
            Project.provider_id.is_not(None),
        )
        return sa.and_(
            CollectionCase.tenant_id == scope.tenant_id,
            CollectionCase.project_id.not_in(provider_project_ids),
        )
    return sa.and_(
        CollectionCase.tenant_id == scope.tenant_id,
        CollectionCase.project_id.in_(_provider_projects(scope)),
    )


def supervisor_agent_filter(scope: SupervisorScope):
    """团队成员（催收员）可见性。"""
    base = sa.and_(
        UserTenantMembership.tenant_id == scope.tenant_id,
        UserTenantMembership.role == "agent",
    )
    if scope.provider_id is None:
        return sa.and_(base, UserTenantMembership.provider_id.is_(None))
    return sa.and_(base, UserTenantMembership.provider_id == scope.provider_id)
```

> 注：`CollectionCase.project_id.not_in(subquery)` 当 `project_id` 为 NULL 时 SQL `NOT IN` 语义会把 NULL 行排除 —— 实现时确认物业侧「无项目案件」仍可见；若 `not_in` 漏 NULL 行，改用 `sa.or_(project_id.is_(None), project_id.not_in(...))`。Step 1 的测试必须覆盖「无项目案件物业侧可见」这一点。

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2 命令，Expected: PASS。修正 `not_in` NULL 语义问题直到测试绿。

- [ ] **Step 5: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/_supervisor_scope.py poc/backend/tests/api/test_supervisor_scope.py
git commit -m "feat(provider-supervisor): 共享 scope helper（case/agent 按物业/服务商分流）"
```

---

## Task 2: `/supervisor/cases` 公海管理 scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor.py`（`list_cases`，约 24-70 行）
- Test: `poc/backend/tests/api/test_supervisor_cases_scope.py`

- [ ] **Step 1: 写失败测试** — 建物业督导 + 服务商督导 + 两侧案件。断言：服务商督导 `GET /supervisor/cases` 只返回本服务商项目案件、`total` 正确、查不到物业案件也查不到别的服务商案件；物业督导仍返回物业案件、不返回服务商案件。沿用 `tests/api/` fixture 风格。

- [ ] **Step 2: 跑测试确认失败** — `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_cases_scope.py -q`，Expected: FAIL（服务商督导现在 403 或返回物业数据）。

- [ ] **Step 3: 改 `supervisor.py`**：
  - 守卫 `require_tenant_roles(*SUPERVISOR_ROLES)` → `require_roles(*SUPERVISOR_ROLES)`（import 改 `require_roles`）。
  - 注入 `scope: Annotated[SupervisorScope, Depends(supervisor_scope)]`。
  - 查询 `.where(CollectionCase.tenant_id == tenant_id)` → `.where(supervisor_case_filter(scope))`。
  - 删掉「Supervisor sees all tenant cases」那行注释。
  - `owner_phone_reveal` 的 `provider_id` 用 `scope.provider_id`。

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2 命令，Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/supervisor.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/supervisor.py poc/backend/tests/api/test_supervisor_cases_scope.py
git commit -m "feat(provider-supervisor): /supervisor/cases scope-aware"
```

---

## Task 3: `/supervisor/live-calls` + force-hangup/takeover scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_live.py`（`list_live_calls` 62、`force-hangup` 123、`takeover` 174）
- Test: `poc/backend/tests/api/test_supervisor_live_scope.py`

- [ ] **Step 1: 写失败测试** — 服务商督导 `GET /supervisor/live-calls` 只见本服务商在途通话；force-hangup/takeover 对非本 scope 的 call 返回 403/404。

- [ ] **Step 2: 跑测试确认失败** — `python3.12 -m pytest tests/api/test_supervisor_live_scope.py -q`。

- [ ] **Step 3: 改 `supervisor_live.py`** — 三个端点守卫换 `require_roles`、注入 `supervisor_scope`。`list_live_calls` 查询经 `CallRecord.case_id → CollectionCase → Project` join 后加 `supervisor_case_filter(scope)`（CallRecord 无直接 provider_id）。force-hangup/takeover：取到目标 call 后，校验其 case 落在 `supervisor_case_filter` 内，否则 403。先 Read 该文件确认查询结构。

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2 命令。

- [ ] **Step 5: commit** — `git commit -m "feat(provider-supervisor): /supervisor/live-calls + 干预端点 scope-aware"`

---

## Task 4: `WS /ws/supervisor` scope 过滤

**Files:**
- Modify: `poc/backend/app/api/ws_supervisor.py`（约 26-71 行）
- Test: `poc/backend/tests/api/test_ws_supervisor_scope.py`（若 WS 难单测，则在现有 ws 测试里加；否则代码自证 + 在 Task 11 E2E 覆盖）

- [ ] **Step 1: 写失败测试或确认测试策略** — 先 Read `ws_supervisor.py` 与现有 ws 测试。WS 推送的 call 事件需按 `supervisor_case_filter` 过滤，服务商督导不应收到物业/别服务商的通话事件。

- [ ] **Step 2-3: 实现** — 连接鉴权解析 `supervisor_scope`；推送前用 `supervisor_case_filter` 判断该 call 是否属本 scope，不属则不推。口径必须与 Task 3 的 HTTP 端点一致。

- [ ] **Step 4-5: 跑测试 + commit** — `git commit -m "feat(provider-supervisor): /ws/supervisor 按 scope 过滤推送"`

---

## Task 5: `/supervisor/reviews` 质检复核 scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_review.py`（`list_reviews` 77、`get` + `label_reviews` 124）
- Test: `poc/backend/tests/api/test_supervisor_reviews_scope.py`

- [ ] **Step 1: 写失败测试** — 服务商督导只见本服务商通话的质检；对非本 scope 的 `call_id` 取详情/PATCH 返回 403/404。

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 改 `supervisor_review.py`** — 三个端点守卫换 `require_roles` + 注入 `supervisor_scope`。查询经 `CallRecord.case_id → CollectionCase → Project` join 加 `supervisor_case_filter(scope)`。详情/PATCH 校验目标 call 在 scope 内。

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: commit** — `git commit -m "feat(provider-supervisor): /supervisor/reviews scope-aware"`

---

## Task 6: `/supervisor/script-labels` 话术反馈 scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_labels.py`（`list_script_labels` 22、`POST .../{feedback_id}`）
- Test: `poc/backend/tests/api/test_supervisor_labels_scope.py`

- [ ] **Step 1-2: 写失败测试 + 跑** — 服务商督导只见本服务商通话的话术反馈。

- [ ] **Step 3: 实现** — 守卫换 `require_roles` + `supervisor_scope`；查询经 `call → case → project` join 加 `supervisor_case_filter`。

- [ ] **Step 4-5: 跑测试 + commit** — `git commit -m "feat(provider-supervisor): /supervisor/script-labels scope-aware"`

---

## Task 7: `/supervisor/risk-events` 风控事件 scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_extras.py`（`list_risk_events` 51、`annotate_risk_event` 93）
- Test: `poc/backend/tests/api/test_supervisor_risk_events_scope.py`

- [ ] **Step 1-2: 写失败测试 + 跑** — 服务商督导只见本服务商通话的风控事件；PATCH 非本 scope 事件 403。

- [ ] **Step 3: 实现** — 守卫换 `require_roles` + `supervisor_scope`；`RiskEvent` 经 `call_id → CallRecord → case → project` join 加 `supervisor_case_filter`。

- [ ] **Step 4-5: 跑测试 + commit** — `git commit -m "feat(provider-supervisor): /supervisor/risk-events scope-aware"`

---

## Task 8: `/supervisor/team-performance` 团队监控 scope-aware（🔴 较重）

**Files:**
- Modify: `poc/backend/app/api/supervisor_extras.py`（`team_performance` 146）
- Test: `poc/backend/tests/api/test_supervisor_team_performance_scope.py`

- [ ] **Step 1-2: 写失败测试 + 跑** — 服务商督导的团队监控只统计本服务商催收员；指标只算本服务商案件/通话。

- [ ] **Step 3: 实现** — 守卫换 `require_roles` + `supervisor_scope`。团队成员列表（原按 `UserTenantMembership.tenant_id + role='agent'`）改用 `supervisor_agent_filter(scope)`。call/case 聚合加 `supervisor_case_filter`。这是改造最重的端点之一，先 Read 全函数理清聚合逻辑再动。

- [ ] **Step 4-5: 跑测试 + commit** — `git commit -m "feat(provider-supervisor): /supervisor/team-performance scope-aware"`

---

## Task 9: `/supervisor/team-stats` 我的 KPI + 团队报表 scope-aware（🔴 较重）

**Files:**
- Modify: `poc/backend/app/api/supervisor_team_stats.py`（`get_team_stats` 33）
- Test: `poc/backend/tests/api/test_supervisor_team_stats_scope.py`

- [ ] **Step 1-2: 写失败测试 + 跑** — 服务商督导团队报表只含本服务商催收员聚合。

- [ ] **Step 3: 实现** — 守卫换 `require_roles` + `supervisor_scope`；agent 聚合用 `supervisor_agent_filter`，call/case 聚合用 `supervisor_case_filter`。

- [ ] **Step 4-5: 跑测试 + commit** — `git commit -m "feat(provider-supervisor): /supervisor/team-stats scope-aware"`

---

## Task 10: 前端 `SUPERVISOR_PROVIDER_NAV`

**Files:**
- Modify: `frontend/src/config/nav.ts`
- Modify: `frontend/src/config/__tests__/nav.test.ts`

- [ ] **Step 1: 写失败测试** — `getNavSections("supervisor", "provider:2")` 的 paths 含 Phase 1 九项功能的 path（`/supervisor/cases`、`/supervisor/live-wall`、`/supervisor/team-performance`、`/supervisor/reviews`、`/supervisor/script-labels`、`/supervisor/risk-events`、`/supervisor/my-kpi`、`/supervisor/stats`、`/supervisor/workspace`），**不含**排班 `/supervisor/shifts`（Phase 2）。物业督导 `tenant:1` 仍返回完整督导 nav。

- [ ] **Step 2: 跑测试确认失败** — `cd frontend && npx vitest run src/config/__tests__/nav.test.ts`。

- [ ] **Step 3: 改 `nav.ts`** — 新增 `SUPERVISOR_PROVIDER_NAV: NavSection[]`（Phase 1 九项，分区参照既有 `NAV_CONFIG.supervisor` 的分组与 icon；标题/label 复用既有督导 nav 文案）。`getNavSections` 里把现在 `role === "supervisor" && s.startsWith("provider:")` 返回的 `[HELP_SECTION]` 改为 `[...SUPERVISOR_PROVIDER_NAV, HELP_SECTION]`。

- [ ] **Step 4: 跑测试确认通过 + typecheck** — `npx vitest run src/config/__tests__/nav.test.ts && npx tsc -p tsconfig.json --noEmit`。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/config/nav.ts frontend/src/config/__tests__/nav.test.ts
git commit -m "feat(provider-supervisor): SUPERVISOR_PROVIDER_NAV（Phase 1 九项）"
```

---

## Task 11: E2E + 全量回归 + 标注 spec

**Files:**
- Modify: `frontend/e2e/per-role-pages.spec.ts`
- Modify: `docs/superpowers/specs/2026-05-17-provider-supervisor-workspace-design.md`

- [ ] **Step 1: E2E 接入** — `per-role-pages.spec.ts` 的 `ROLE_CASES` 给服务商督导账号 `13000000012` 加角色项，`pages` 含 Phase 1 几个关键页（`/supervisor/cases`、`/supervisor/reviews`、`/supervisor/team-performance` 等），`expectText` 用稳定文案。

- [ ] **Step 2: 后端全量回归** — `cd poc/backend && python3.12 -m pytest -q`，Expected: 全绿（含所有新增 scope 测试 + 既有测试无回归——特别确认物业督导相关测试未被改坏）。

- [ ] **Step 3: 前端回归 + lint** — `cd frontend && npx vitest run && npm run lint && npx tsc -p tsconfig.json --noEmit`。

- [ ] **Step 4: 标注 spec** — 设计文档末尾加：`> ✅ Phase 1 已实现(日期)：9 项 /supervisor/* 端点 scope-aware + SUPERVISOR_PROVIDER_NAV。Phase 2（排班）待启动。`

- [ ] **Step 5: commit** — `git commit -m "test(provider-supervisor): E2E 接入 + Phase 1 标注 spec"`

---

## Self-Review

**Spec 覆盖**：Task 1 = 共享 helper（架构核心）；Task 2-9 = Phase 1 的 9 项功能对应 11 个端点（公海/案件、实时通话墙3端点、WS、质检复核3端点、话术反馈、风控2端点、团队监控、团队报表/KPI）；Task 10 = 前端 nav；Task 11 = E2E + 回归。督导工作台（聚合页）依赖 Task 2-9 端点改完即生效，无独立任务。Phase 2（排班）按设计文档独立成计划，不在本计划。

**占位符扫描**：Task 3-9 的「先 Read 该文件确认查询结构」是针对既有端点真实代码的必要核对指令（每个端点的 join 路径略有差异），非占位符 —— 改造模式由 Task 1 的 helper + Task 2 的完整范例确立。Task 4 的 WS 测试策略待实施时按 `ws_supervisor.py` 真实可测性定，已给兜底（E2E 覆盖）。

**类型/口径一致性**：`SupervisorScope`、`supervisor_scope`、`supervisor_case_filter`、`supervisor_agent_filter` 在 Task 1 定义，Task 2-9 一致引用。守卫统一 `require_roles(*SUPERVISOR_ROLES)`（凡含 supervisor 跨两侧端点）。多租户隔离测试每个端点必配。

**多租户铁律**：每个 scope 测试必须断言「服务商 A 督导查不到服务商 B、查不到物业」三向隔离。
