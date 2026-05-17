# 减免归属 + 审批流物业侧强制 + 佣金不计减免 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给减免（DiscountOffer）加服务商归属、把减免审批收紧为物业专属、把两处佣金计算改为「实收金额 × 项目级佣金率」。

**Architecture:** 后端单子项目，无前端 / Android 改动。一条 Alembic 迁移加 3 列（`discount_offer.provider_id` + `project` 两个佣金率列）；新建 `app/services/commission.py` 收口「实收金额推导」与「项目佣金率解析」；改动落在既有 `discount_offers.py` / `admin.py` / `provider_admin.py` / 相关 schema。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL；pytest + testcontainers-postgres。

**源 spec:** `docs/superpowers/specs/2026-05-16-discount-attribution-commission-design.md`（commit `b41195c`）。

---

## 关键工程约定（每个 task 都适用）

- 测试从 `poc/backend/` 运行：`python3.12 -m pytest <path> -v`。
- 测试 DB 由 `Base.metadata.create_all(engine)`（ORM）建表，**不跑迁移** —— 模型列改对了测试就能过；迁移文件由 code review 把关与模型保持一致。
- 自定义 HTTPException handler 返回**扁平** body `{"code","message"}` —— 测试断言 `resp.json()["code"]`，**不是** `resp.json()["detail"]["code"]`。
- 错误码沿用既有风格（`ERR_NOT_FOUND` / `ERR_FORBIDDEN` / `ERR_NO_TENANT` …）。
- 所有 DB 查询带 `tenant_id`（佣金查询本就带）；手机号脱敏沿用 `mask_phone`。
- Conventional Commits；每个 task 末尾单独 commit。

## File Structure

| 文件 | 责任 | Task |
|------|------|------|
| `poc/backend/alembic/versions/24018_v220_discount_provider_commission_rates.py` | 建：3 列迁移 | 1 |
| `poc/backend/app/models/discount_offer.py` | 改：`DiscountOffer` 加 `provider_id` | 1 |
| `poc/backend/app/models/case.py` | 改：`Project` 加 2 个佣金率列 | 1 |
| `poc/backend/app/schemas/discount.py` | 改：`DiscountOfferOut` 加 `provider_id` | 2 |
| `poc/backend/app/api/discount_offers.py` | 改：create 写 `provider_id`；approve/reject/escalate 守卫收紧 | 2, 3 |
| `poc/backend/app/services/commission.py` | 建：实收推导 + 佣金率解析 | 4 |
| `poc/backend/app/api/admin.py` | 改：`agent-commissions` 逐案按项目率 + 扣减免 | 5 |
| `poc/backend/app/schemas/provider_admin.py` | 改：`CommissionLineItem` 加 `commission_rate`；建 `ProjectCommissionRateIn` | 6, 7 |
| `poc/backend/app/api/provider_admin.py` | 改：`team/{id}/commission` 逐案计算；新增 D2 写端点 | 6, 7 |
| `poc/backend/app/schemas/project.py` | 改：`ProjectCreateIn`/`ProjectUpdateIn`/`ProjectOut` 加佣金率字段 | 7 |
| `poc/backend/app/api/admin_projects.py` | 改：`create_project` 构造器加 D1 字段 | 7 |
| `poc/backend/tests/...` | 建：§10 全部测试 | 1-7 |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | 改：§9.2 标注已实现 | 8 |

---

## Task 1: 迁移 + 模型三列

**Files:**
- Create: `poc/backend/alembic/versions/24018_v220_discount_provider_commission_rates.py`
- Modify: `poc/backend/app/models/discount_offer.py:43`（`case_id` 列之后）
- Modify: `poc/backend/app/models/case.py:80`（`late_fee_waive_disabled` 列之后、`__table_args__` 之前）
- Test: `poc/backend/tests/test_discount_provider_commission_models.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/test_discount_provider_commission_models.py`:

```python
"""§9.2 Task 1 — DiscountOffer.provider_id + Project 佣金率两列 round-trip。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.crypto import encrypt_phone


def _make_provider(db_session):
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="测试律所92",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900092001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


def test_discount_offer_provider_id_round_trip(db_session, seeded_tenant, seeded_case):
    from app.models.discount_offer import DiscountOffer

    provider = _make_provider(db_session)
    offer = DiscountOffer(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        provider_id=provider.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal("800.00"),
        discount_pct=20,
        reason="家庭困难，申请减免",
        status="pending_supervisor",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    db_session.refresh(offer)

    got = db_session.get(DiscountOffer, offer.id)
    assert got is not None
    assert got.provider_id == provider.id


def test_discount_offer_provider_id_defaults_null(db_session, seeded_tenant, seeded_case):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("500.00"),
        proposed_amount=Decimal("500.00"),
        discount_pct=0,
        reason="物业内勤发起减免",
        status="approved",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    db_session.refresh(offer)
    assert offer.provider_id is None


def test_project_commission_rate_columns_round_trip(db_session, seeded_tenant):
    from app.models.case import Project

    project = Project(
        tenant_id=seeded_tenant.id,
        name="§9.2 佣金率测试项目",
        internal_agent_commission_rate=Decimal("0.0800"),
        provider_agent_commission_rate=Decimal("0.1200"),
    )
    db_session.add(project)
    db_session.flush()
    db_session.refresh(project)

    got = db_session.get(Project, project.id)
    assert got.internal_agent_commission_rate == Decimal("0.0800")
    assert got.provider_agent_commission_rate == Decimal("0.1200")


def test_project_commission_rate_columns_default_null(db_session, seeded_tenant):
    from app.models.case import Project

    project = Project(tenant_id=seeded_tenant.id, name="§9.2 无佣金率项目")
    db_session.add(project)
    db_session.flush()
    db_session.refresh(project)
    assert project.internal_agent_commission_rate is None
    assert project.provider_agent_commission_rate is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/test_discount_provider_commission_models.py -v`
Expected: FAIL — `TypeError: 'provider_id' is an invalid keyword argument for DiscountOffer`（以及 Project 同类报错）。

- [ ] **Step 3: 给 `DiscountOffer` 加 `provider_id` 列**

In `poc/backend/app/models/discount_offer.py`, after the `case_id` `mapped_column` block (ends at line 43, before `applicant_user_id`), insert:

```python
    # §9.2-A — 减免归属：NULL = 物业内勤发起；非 NULL = 服务商催收员发起，值为其服务商 id
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 4: 给 `Project` 加两个佣金率列**

In `poc/backend/app/models/case.py`, after `late_fee_waive_disabled` (line 80) and before `__table_args__` (line 82), insert:

```python

    # §9.2 D1/D2 — 项目级佣金率（NUMERIC(6,4)，NULL 时回退系统默认 0.05）
    internal_agent_commission_rate: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(6, 4))
    provider_agent_commission_rate: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(6, 4))
```

- [ ] **Step 5: 写迁移文件**

Create `poc/backend/alembic/versions/24018_v220_discount_provider_commission_rates.py`:

```python
"""§9.2 — discount_offer.provider_id + project 佣金率两列

Revision ID: 24018v220d
Revises: 24017v220c
Create Date: 2026-05-17 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24018v220d"
down_revision: str | None = "24017v220c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discount_offer",
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_discount_offer_provider",
        "discount_offer",
        "service_provider",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "project",
        sa.Column("internal_agent_commission_rate", sa.Numeric(6, 4), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("provider_agent_commission_rate", sa.Numeric(6, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project", "provider_agent_commission_rate")
    op.drop_column("project", "internal_agent_commission_rate")
    op.drop_constraint("fk_discount_offer_provider", "discount_offer", type_="foreignkey")
    op.drop_column("discount_offer", "provider_id")
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python3.12 -m pytest tests/test_discount_provider_commission_models.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 7: 校验迁移可被 alembic 识别**

Run: `python3.12 -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s = ScriptDirectory.from_config(Config('alembic.ini')); print(s.get_current_head())"`
Expected: 打印 `24018v220d`（确认新迁移成为唯一 head、链不断）。

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/alembic/versions/24018_v220_discount_provider_commission_rates.py poc/backend/app/models/discount_offer.py poc/backend/app/models/case.py poc/backend/tests/test_discount_provider_commission_models.py
git commit -m "feat(§9.2): 减免 provider_id + 项目级佣金率两列 + 迁移 24018v220d"
```

---

## Task 2: Part A — 减免归属（create 写入 + 透出）

**Files:**
- Modify: `poc/backend/app/schemas/discount.py:64`（`created_at` 字段附近，`DiscountOfferOut` 内）
- Modify: `poc/backend/app/api/discount_offers.py:289-306`（`create_offer` 构造 `DiscountOffer`）
- Test: `poc/backend/tests/api/test_discount_offers_attribution.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_discount_offers_attribution.py`:

```python
"""§9.2 Task 2 — 减免归属：create 写 provider_id + DiscountOfferOut 透出。"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone


def _provider(db_session):
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="归属测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092010"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


def _provider_agent_headers(db_session, tenant_id, provider_id):
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900092011"),
        name="服务商催收员",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role="agent",
            work_mode="external",
            provider_id=provider_id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": "agent",
            "provider_id": provider_id,
            "scope": f"provider:{provider_id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


_BODY = {
    "offer_type": "principal_discount",
    "original_amount": "1000.00",
    "proposed_amount": "800.00",
    "reason": "业主主张房屋空置，申请减免",
}


@pytest.mark.anyio
async def test_provider_agent_offer_carries_provider_id(
    client, db_session, seeded_tenant, seeded_case
):
    provider = _provider(db_session)
    headers = _provider_agent_headers(db_session, seeded_tenant.id, provider.id)

    resp = await client.post(
        f"/api/v1/cases/{seeded_case.id}/discount-offers", json=_BODY, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_id"] == provider.id


@pytest.mark.anyio
async def test_property_agent_offer_provider_id_null(
    client, seeded_case, agent_auth_headers
):
    resp = await client.post(
        f"/api/v1/cases/{seeded_case.id}/discount-offers",
        json=_BODY,
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_id"] is None
```

> 注：`client` 是 conftest 的 async 测试客户端；`agent_auth_headers` 是物业内勤 token（无 `provider_id`）。`@pytest.mark.anyio` 与项目既有 async API 测试一致；若既有测试不带该标记（`asyncio_mode="auto"`），实现者按同目录其他 `tests/api/*` 测试的写法对齐即可。

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/api/test_discount_offers_attribution.py -v`
Expected: FAIL — 响应 JSON 无 `provider_id` 键（`KeyError`）。

- [ ] **Step 3: `DiscountOfferOut` 加 `provider_id`**

In `poc/backend/app/schemas/discount.py`, inside `DiscountOfferOut`, add the field right after `case_id: int`:

```python
    provider_id: int | None = None
```

- [ ] **Step 4: `create_offer` 构造器写入 `provider_id`**

In `poc/backend/app/api/discount_offers.py`, the `DiscountOffer(...)` constructor in `create_offer` (starts line 289) — add `provider_id` right after `case_id=case_id,`:

```python
    offer = DiscountOffer(
        tenant_id=int(tenant_id),
        case_id=case_id,
        provider_id=payload.get("provider_id"),
        applicant_user_id=user_id,
```

> `_to_out` 用 `DiscountOfferOut.model_validate(offer, from_attributes=True)` —— 模型（Task 1）+ schema 都有 `provider_id` 后自动透出，无需改 `_to_out`。物业内勤 token 无 `provider_id` → `payload.get(...)` 返回 `None`。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3.12 -m pytest tests/api/test_discount_offers_attribution.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/discount.py poc/backend/app/api/discount_offers.py poc/backend/tests/api/test_discount_offers_attribution.py
git commit -m "feat(§9.2-A): 减免创建写入 provider_id 归属并透出"
```

---

## Task 3: Part B — 审批流物业侧强制

**Files:**
- Modify: `poc/backend/app/api/discount_offers.py:25`（import）、`:404` `:455` `:503`（三个端点守卫）
- Test: `poc/backend/tests/api/test_discount_offers_approval_guard.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_discount_offers_approval_guard.py`:

```python
"""§9.2 Task 3 — 减免 approve/reject/escalate 收紧为物业侧专属。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _pending_offer(db_session, tenant_id, case_id):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=tenant_id,
        case_id=case_id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal("700.00"),
        discount_pct=30,
        reason="测试审批守卫用减免",
        status="pending_supervisor",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        audit_trail=[],
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def _provider_supervisor_headers(db_session, tenant_id):
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="审批守卫测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092020"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()
    user = UserAccount(
        phone_enc=encrypt_phone("13900092021"),
        name="服务商督导",
        password_hash=get_password_hash("Super@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role="supervisor",
            provider_id=provider.id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": "supervisor",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_provider_supervisor_cannot_approve(
    client, db_session, seeded_tenant, seeded_case
):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/approve", json={}, headers=headers
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.anyio
async def test_provider_supervisor_cannot_reject(
    client, db_session, seeded_tenant, seeded_case
):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/reject",
        json={"reason": "驳回理由"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.anyio
async def test_provider_supervisor_cannot_escalate(
    client, db_session, seeded_tenant, seeded_case
):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/escalate", json={}, headers=headers
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.anyio
async def test_property_supervisor_can_approve(
    client, db_session, seeded_tenant, seeded_case, supervisor_auth_headers
):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/approve",
        json={},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/api/test_discount_offers_approval_guard.py -v`
Expected: 三个 `provider_supervisor_cannot_*` FAIL（旧守卫 `require_roles` 放行服务商督导，返回 200/409 而非 403）。`test_property_supervisor_can_approve` 应已 PASS。

- [ ] **Step 3: import `require_tenant_roles`**

In `poc/backend/app/api/discount_offers.py` line 25, change:

```python
from app.core.security import get_token_payload, require_roles
```
to:
```python
from app.core.security import get_token_payload, require_roles, require_tenant_roles
```

- [ ] **Step 4: 收紧三个端点守卫**

In `poc/backend/app/api/discount_offers.py`, in `approve_offer`、`reject_offer`、`escalate_offer` 三个函数签名里，把这一行：

```python
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
```
各自替换为：
```python
    _user: Annotated[object, Depends(require_tenant_roles("supervisor", "admin", "superadmin"))],
```

> 只改这三个端点。`create_offer` / `list_offers` / `get_offer` / `mark_executed` 的 `require_roles(*ALL_ROLES)` 守卫**保持不动** —— 服务商催收员仍可发起减免、双方仍可查询、标记已执行不变。端点内部 `offer.status` 与角色的分层校验（`pending_supervisor` 须 supervisor 等）也保持不动。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3.12 -m pytest tests/api/test_discount_offers_approval_guard.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/discount_offers.py poc/backend/tests/api/test_discount_offers_approval_guard.py
git commit -m "feat(§9.2-B): 减免审批/拒绝/升级收紧为物业侧专属"
```

---

## Task 4: 佣金服务模块

**Files:**
- Create: `poc/backend/app/services/commission.py`
- Test: `poc/backend/tests/services/test_commission.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/services/test_commission.py`:

```python
"""§9.2 Task 4 — app/services/commission.py 单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _offer(db_session, tenant_id, case_id, *, proposed, status):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=tenant_id,
        case_id=case_id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal(proposed),
        discount_pct=10,
        reason="commission service 测试减免",
        status=status,
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        audit_trail=[],
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def test_executed_discount_amounts_empty_list(db_session):
    from app.services.commission import executed_discount_amounts

    assert executed_discount_amounts(db_session, []) == {}


def test_executed_discount_amounts_returns_proposed_for_executed(
    db_session, seeded_tenant, seeded_case
):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="executed")
    result = executed_discount_amounts(db_session, [seeded_case.id])
    assert result == {seeded_case.id: Decimal("600.00")}


def test_executed_discount_amounts_skips_non_executed(
    db_session, seeded_tenant, seeded_case
):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="approved")
    assert executed_discount_amounts(db_session, [seeded_case.id]) == {}


def test_executed_discount_amounts_latest_wins(db_session, seeded_tenant, seeded_case):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="executed")
    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="550.00", status="executed")
    result = executed_discount_amounts(db_session, [seeded_case.id])
    assert result == {seeded_case.id: Decimal("550.00")}


def test_internal_agent_rate(db_session, seeded_tenant):
    from app.models.case import Project
    from app.services.commission import DEFAULT_COMMISSION_RATE, internal_agent_rate

    p_rate = Project(
        tenant_id=seeded_tenant.id,
        name="有内勤率项目",
        internal_agent_commission_rate=Decimal("0.0900"),
    )
    p_null = Project(tenant_id=seeded_tenant.id, name="无内勤率项目")
    db_session.add_all([p_rate, p_null])
    db_session.flush()

    assert internal_agent_rate(p_rate) == Decimal("0.0900")
    assert internal_agent_rate(p_null) == DEFAULT_COMMISSION_RATE
    assert internal_agent_rate(None) == DEFAULT_COMMISSION_RATE


def test_provider_agent_rate(db_session, seeded_tenant):
    from app.models.case import Project
    from app.services.commission import DEFAULT_COMMISSION_RATE, provider_agent_rate

    p_rate = Project(
        tenant_id=seeded_tenant.id,
        name="有服务商率项目",
        provider_agent_commission_rate=Decimal("0.1500"),
    )
    p_null = Project(tenant_id=seeded_tenant.id, name="无服务商率项目")
    db_session.add_all([p_rate, p_null])
    db_session.flush()

    assert provider_agent_rate(p_rate) == Decimal("0.1500")
    assert provider_agent_rate(p_null) == DEFAULT_COMMISSION_RATE
    assert provider_agent_rate(None) == DEFAULT_COMMISSION_RATE
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/services/test_commission.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.commission'`。

- [ ] **Step 3: 写佣金服务模块**

Create `poc/backend/app/services/commission.py`:

```python
"""§9.2 — 佣金计算共用逻辑。

收口两处佣金端点（物业内勤 admin.py / 服务商 provider_admin.py）的：
- 「实收金额」推导（扣已执行减免）；
- 「按项目佣金率」解析（D1 内勤率 / D2 服务商率，NULL 回退系统默认）。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Project
from app.models.discount_offer import DiscountOffer

DEFAULT_COMMISSION_RATE = Decimal("0.05")


def executed_discount_amounts(db: Session, case_ids: list[int]) -> dict[int, Decimal]:
    """case_id → 业主实收额，仅含有 status='executed' 减免的案件。

    §9.2-C：减免部分不计佣金 —— 已执行减免的案件，实收 = 该减免的
    proposed_amount（业主实际缴的钱）。无已执行减免的案件不在返回 dict 内，
    调用方回退 amount_owed。多条 executed（罕见）→ 按 id 升序遍历，最新 id 胜出。
    """
    if not case_ids:
        return {}
    rows = db.execute(
        select(DiscountOffer.case_id, DiscountOffer.proposed_amount)
        .where(
            DiscountOffer.case_id.in_(case_ids),
            DiscountOffer.status == "executed",
        )
        .order_by(DiscountOffer.id)
    ).all()
    result: dict[int, Decimal] = {}
    for case_id, proposed_amount in rows:
        result[case_id] = Decimal(str(proposed_amount or 0))
    return result


def internal_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D1：项目级内勤佣金率；NULL / 无项目 → 系统默认 0.05。"""
    if project is not None and project.internal_agent_commission_rate is not None:
        return Decimal(str(project.internal_agent_commission_rate))
    return DEFAULT_COMMISSION_RATE


def provider_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D2：项目级服务商催收员佣金率；NULL / 无项目 → 系统默认 0.05。"""
    if project is not None and project.provider_agent_commission_rate is not None:
        return Decimal(str(project.provider_agent_commission_rate))
    return DEFAULT_COMMISSION_RATE
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.12 -m pytest tests/services/test_commission.py -v`
Expected: PASS（6 passed）。

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/commission.py poc/backend/tests/services/test_commission.py
git commit -m "feat(§9.2-C): 新增 commission 服务 — 实收推导 + 项目佣金率解析"
```

---

## Task 5: 内勤佣金计算改造（admin.py）

**Files:**
- Modify: `poc/backend/app/api/admin.py:616-684`（`list_agent_commissions`）
- Test: `poc/backend/tests/api/test_admin_agent_commissions.py`

> `INTERNAL_AGENT_COMMISSION_RATE = 0.05`（line 600）**保留不删** —— `get_agent_commission_detail` 与账单汇总仍引用它，且 §9.2 spec §7 只点名 `list_agent_commissions` 一处。本 task 不改 detail 端点与账单汇总（spec 明确范围）。

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_admin_agent_commissions.py`:

```python
"""§9.2 Task 5 — /admin/agent-commissions 逐案按项目率 + 扣减免。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest


def _project(db_session, tenant_id, name, internal_rate):
    from app.models.case import Project

    p = Project(tenant_id=tenant_id, name=name, internal_agent_commission_rate=internal_rate)
    db_session.add(p)
    db_session.flush()
    return p


def _paid_case(db_session, tenant_id, owner_id, agent_id, project_id, amount_owed):
    from app.models.case import CollectionCase

    case = CollectionCase(
        tenant_id=tenant_id,
        owner_id=owner_id,
        project_id=project_id,
        assigned_to=agent_id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal(amount_owed),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    db_session.add(case)
    db_session.flush()
    return case


def _executed_offer(db_session, tenant_id, case_id, proposed):
    from app.models.discount_offer import DiscountOffer

    db_session.add(
        DiscountOffer(
            tenant_id=tenant_id,
            case_id=case_id,
            applicant_user_id=None,
            applicant_role="agent",
            offer_type="principal_discount",
            original_amount=Decimal("1000.00"),
            proposed_amount=Decimal(proposed),
            discount_pct=10,
            reason="内勤佣金测试减免",
            status="executed",
            approver_role_required="supervisor",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            audit_trail=[],
        )
    )
    db_session.flush()


@pytest.mark.anyio
async def test_agent_commission_per_case_rate_and_discount(
    client, db_session, seeded_tenant, seeded_owner, seeded_member_user, admin_auth_headers
):
    # 项目 P1：内勤率 0.08；P2：NULL → 默认 0.05
    p1 = _project(db_session, seeded_tenant.id, "佣金项目甲", Decimal("0.0800"))
    p2 = _project(db_session, seeded_tenant.id, "佣金项目乙", None)
    # C1：欠 1000，有已执行减免 → 实收 600；归 P1
    c1 = _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p1.id, "1000.00"
    )
    _executed_offer(db_session, seeded_tenant.id, c1.id, "600.00")
    # C2：欠 2000，无减免；归 P2
    _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p2.id, "2000.00"
    )

    resp = await client.get(
        "/api/v1/admin/agent-commissions?year_month=2026-05", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    item = next(it for it in body["items"] if it["user_id"] == seeded_member_user.id)
    assert item["paid_case_count"] == 2
    # base = 实收 600 + 2000 = 2600
    assert Decimal(item["base_amount"]) == Decimal("2600.00")
    # commission = (600*0.08).q(.01) + (2000*0.05).q(.01) = 48.00 + 100.00
    assert Decimal(item["commission"]) == Decimal("148.00")
    assert Decimal(str(body["total_base"])) == Decimal("2600.00")
    assert Decimal(str(body["total_commission"])) == Decimal("148.00")
```

> `seeded_member_user` 是 `seeded_tenant` 下唯一的 internal agent；`admin_auth_headers` 是物业 admin token。`CollectionCase` 必填字段以 conftest `seeded_case` fixture 为准（`pool_type`/`stage`/`amount_owed`/`months_overdue`/`priority_score`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/api/test_admin_agent_commissions.py -v`
Expected: FAIL — 旧算法用 `amount_owed`（不扣减免）× 单一 `0.05`：`base=3000`、`commission=150.00`，与断言不符。

- [ ] **Step 3: 改写 `list_agent_commissions`**

In `poc/backend/app/api/admin.py`, replace the whole `list_agent_commissions` function body (lines 616-684) with:

```python
@router.get("/agent-commissions", response_model=AgentCommissionList)
async def list_agent_commissions(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> AgentCommissionList:
    """v1.5.6 — 物业内部催收员当月提成（应发员工工资视图）。

    §9.2-C/D1 — 佣金基数改用「实收金额」（扣已执行减免），佣金率改为逐案按
    项目级 internal_agent_commission_rate（NULL 回退系统默认 0.05）。
    AgentCommissionItem.commission_rate 透出为该 agent 的加权有效率。
    """
    from decimal import Decimal as D

    from app.core.crypto import mask_phone
    from app.models.case import CollectionCase, Project
    from app.services.commission import executed_discount_amounts, internal_agent_rate

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    period_start, period_end = _month_window(year_month)

    agents = db.execute(
        select(UserAccount, UserTenantMembership)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role == "agent",
            UserTenantMembership.work_mode == "internal",
            UserTenantMembership.is_active.is_(True),
            UserAccount.is_active.is_(True),
        )
        .order_by(UserAccount.id)
    ).all()

    # 项目缓存：跨 agent 复用，避免 N+1
    project_cache: dict[int, Project | None] = {}

    def _project(project_id: int | None) -> Project | None:
        if project_id is None:
            return None
        if project_id not in project_cache:
            project_cache[project_id] = db.get(Project, project_id)
        return project_cache[project_id]

    items: list[AgentCommissionItem] = []
    for u, _m in agents:
        rows = db.execute(
            select(
                CollectionCase.id,
                CollectionCase.amount_owed,
                CollectionCase.project_id,
            ).where(
                CollectionCase.assigned_to == u.id,
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= period_start,
                CollectionCase.updated_at < period_end,
            )
        ).all()
        executed = executed_discount_amounts(db, [r[0] for r in rows])
        base = D("0")
        commission = D("0")
        for case_id, amount_owed, project_id in rows:
            collected = executed.get(case_id) or D(str(amount_owed or 0))
            rate = internal_agent_rate(_project(project_id))
            base += collected
            commission += (collected * rate).quantize(D("0.01"))
        effective_rate = (
            float(commission / base) if base > 0 else INTERNAL_AGENT_COMMISSION_RATE
        )
        items.append(
            AgentCommissionItem(
                user_id=u.id,
                name=u.name,
                phone_masked=mask_phone(u.phone_enc),
                year_month=year_month,
                commission_rate=effective_rate,
                base_amount=base,
                paid_case_count=len(rows),
                commission=commission,
            )
        )
    total_base = sum((it.base_amount for it in items), D("0"))
    total_commission = sum((it.commission for it in items), D("0"))
    return AgentCommissionList(
        year_month=year_month,
        total_base=total_base,
        total_commission=total_commission,
        items=items,
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3.12 -m pytest tests/api/test_admin_agent_commissions.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: 跑 admin.py 既有回归**

Run: `python3.12 -m pytest tests/api/ -k admin -q`
Expected: 全绿（确认未破坏 `agent-commissions/{user_id}` detail 与账单汇总等既有端点）。

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/admin.py poc/backend/tests/api/test_admin_agent_commissions.py
git commit -m "feat(§9.2-C/D1): 内勤佣金改为逐案实收×项目率"
```

---

## Task 6: 服务商佣金计算改造（provider_admin.py）

**Files:**
- Modify: `poc/backend/app/schemas/provider_admin.py:144-149`（`CommissionLineItem`）
- Modify: `poc/backend/app/api/provider_admin.py:731-800`（`get_member_commission`）
- Test: `poc/backend/tests/api/test_provider_member_commission.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_provider_member_commission.py`:

```python
"""§9.2 Task 6 — /provider/team/{id}/commission 逐案实收×服务商项目率。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _seed(db_session, seeded_tenant, seeded_owner):
    """造：服务商 + 服务商 admin（调用方）+ 团队成员 + 2 个项目 + 2 个已付案件 + 1 条已执行减免。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.case import CollectionCase, Project
    from app.models.discount_offer import DiscountOffer
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="服务商佣金测试",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092030"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()

    caller = UserAccount(
        phone_enc=encrypt_phone("13900092031"),
        name="服务商管理员",
        password_hash=get_password_hash("Admin@1234"),
        is_active=True,
    )
    member = UserAccount(
        phone_enc=encrypt_phone("13900092032"),
        name="服务商催收员",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add_all([caller, member])
    db_session.flush()
    db_session.add_all(
        [
            UserTenantMembership(
                user_id=caller.id,
                tenant_id=seeded_tenant.id,
                role="admin",
                provider_id=provider.id,
                is_active=True,
            ),
            UserTenantMembership(
                user_id=member.id,
                tenant_id=seeded_tenant.id,
                role="agent",
                work_mode="external",
                provider_id=provider.id,
                is_active=True,
            ),
        ]
    )

    p1 = Project(
        tenant_id=seeded_tenant.id,
        name="服务商项目甲",
        provider_id=provider.id,
        provider_agent_commission_rate=Decimal("0.1000"),
    )
    p2 = Project(tenant_id=seeded_tenant.id, name="服务商项目乙", provider_id=provider.id)
    db_session.add_all([p1, p2])
    db_session.flush()

    c1 = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        project_id=p1.id,
        assigned_to=member.id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal("1000.00"),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    c2 = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        project_id=p2.id,
        assigned_to=member.id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal("2000.00"),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    db_session.add(
        DiscountOffer(
            tenant_id=seeded_tenant.id,
            case_id=c1.id,
            provider_id=provider.id,
            applicant_user_id=None,
            applicant_role="agent",
            offer_type="principal_discount",
            original_amount=Decimal("1000.00"),
            proposed_amount=Decimal("600.00"),
            discount_pct=40,
            reason="服务商佣金测试减免",
            status="executed",
            approver_role_required="supervisor",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            audit_trail=[],
        )
    )
    db_session.flush()

    token = create_access_token(
        {
            "sub": str(caller.id),
            "user_id": caller.id,
            "tenant_id": None,
            "role": "admin",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}, member.id


@pytest.mark.anyio
async def test_provider_member_commission_per_case(
    client, db_session, seeded_tenant, seeded_owner
):
    headers, member_id = _seed(db_session, seeded_tenant, seeded_owner)

    resp = await client.get(
        f"/api/v1/provider/team/{member_id}/commission?year_month=2026-05", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # base = 实收 600 + 2000 = 2600
    assert Decimal(str(body["base_amount"])) == Decimal("2600.00")
    # commission = (600*0.10).q(.01) + (2000*0.05).q(.01) = 60.00 + 100.00
    assert Decimal(str(body["commission"])) == Decimal("160.00")
    assert len(body["items"]) == 2

    by_amount = {Decimal(str(it["paid_amount"])): it for it in body["items"]}
    # C1 实收 600，项目率 0.10
    assert Decimal(str(by_amount[Decimal("600.00")]["commission_rate"])) == Decimal("0.1000")
    # C2 实收 2000，项目无率 → 默认 0.05
    assert Decimal(str(by_amount[Decimal("2000.00")]["commission_rate"])) == Decimal("0.0500")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/api/test_provider_member_commission.py -v`
Expected: FAIL — 旧算法 `base=3000`、单率 `0.05`、`commission=150.00`，且 `CommissionLineItem` 无 `commission_rate` 键。

- [ ] **Step 3: `CommissionLineItem` 加 `commission_rate`**

In `poc/backend/app/schemas/provider_admin.py`, change `CommissionLineItem`:

```python
class CommissionLineItem(BaseModel):
    case_id: int
    owner_name: str
    paid_amount: Decimal
    paid_at: datetime | None
    commission_rate: Decimal  # §9.2 — 该案所属项目的服务商佣金率
```

- [ ] **Step 4: 改写 `get_member_commission`**

In `poc/backend/app/api/provider_admin.py`, replace the body of `get_member_commission` (lines 735-800) from after the signature with:

```python
async def get_member_commission(
    member_user_id: int,
    year_month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderMemberCommission:
    """§9.2-C/D2 — 服务商单成员当月佣金。

    逐案件：实收（扣已执行减免）× 该案项目的 provider_agent_commission_rate
    （NULL 回退系统默认 0.05），求和。commission_rate 透出加权有效率。
    """
    from app.models.case import Project
    from app.services.commission import executed_discount_amounts, provider_agent_rate

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # Verify member belongs to this provider
    row = db.execute(
        select(UserAccount)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == member_user_id,
            UserTenantMembership.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "团队成员不存在"},
        )
    member = row[0]

    year, month = (int(p) for p in year_month.split("-"))
    period_start = datetime(year, month, 1, tzinfo=UTC)
    period_end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )

    # Settled cases assigned to this user, paid in target month
    case_rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.assigned_to == member_user_id)
        .where(CollectionCase.stage == "paid")
        .where(CollectionCase.updated_at >= period_start)
        .where(CollectionCase.updated_at < period_end)
    ).all()

    executed = executed_discount_amounts(db, [c.id for c, _o in case_rows])
    project_cache: dict[int, Project | None] = {}

    def _project(project_id: int | None) -> Project | None:
        if project_id is None:
            return None
        if project_id not in project_cache:
            project_cache[project_id] = db.get(Project, project_id)
        return project_cache[project_id]

    items: list[CommissionLineItem] = []
    base = Decimal("0")
    commission = Decimal("0")
    for c, o in case_rows:
        collected = executed.get(c.id) or Decimal(str(c.amount_owed or 0))
        rate = provider_agent_rate(_project(c.project_id))
        base += collected
        commission += (collected * rate).quantize(Decimal("0.01"))
        items.append(
            CommissionLineItem(
                case_id=c.id,
                owner_name=o.name,
                paid_amount=collected,
                paid_at=c.updated_at,
                commission_rate=rate,
            )
        )
    effective_rate = float(commission / base) if base > 0 else DEFAULT_COMMISSION_RATE

    return ProviderMemberCommission(
        user_id=member.id,
        name=member.name,
        year_month=year_month,
        commission_rate=effective_rate,
        base_amount=base,
        commission=commission,
        items=items,
    )
```

> `DEFAULT_COMMISSION_RATE`（`provider_admin.py` 模块级，float `0.05`）仅用于 base==0 时的兜底有效率。`paid_amount` 改为透出**实收额 `collected`**（不再是原始 `amount_owed`）。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3.12 -m pytest tests/api/test_provider_member_commission.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 6: 跑 provider_admin 既有回归**

Run: `python3.12 -m pytest tests/api/test_provider_admin.py tests/api/test_provider_admin_extras.py -q`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/provider_admin.py poc/backend/app/api/provider_admin.py poc/backend/tests/api/test_provider_member_commission.py
git commit -m "feat(§9.2-C/D2): 服务商佣金改为逐案实收×项目率"
```

---

## Task 7: D1 / D2 — 佣金率按项目可配（写端点）

**Files:**
- Modify: `poc/backend/app/schemas/project.py`（`ProjectCreateIn` / `ProjectUpdateIn` / `ProjectOut`）
- Modify: `poc/backend/app/api/admin_projects.py:248-278`（`create_project` 构造器）
- Modify: `poc/backend/app/schemas/provider_admin.py`（新增 `ProjectCommissionRateIn`）
- Modify: `poc/backend/app/api/provider_admin.py`（新增 D2 端点，置于 `assign_provider_pm` 之后、文件末尾）
- Test: `poc/backend/tests/api/test_project_commission_rates.py`

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_project_commission_rates.py`:

```python
"""§9.2 Task 7 — D1 物业改内勤率 / D2 服务商改服务商率。"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _project(db_session, tenant_id, name, provider_id=None):
    from app.models.case import Project

    p = Project(tenant_id=tenant_id, name=name, provider_id=provider_id)
    db_session.add(p)
    db_session.flush()
    return p


def _provider_pm_headers(db_session, tenant_id, *, name_suffix, role="project_manager"):
    """造一个服务商 + 该服务商下 role 角色用户，返回 (headers, provider_id)。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name=f"D2测试服务商{name_suffix}",
        provider_type="collection",
        admin_phone_enc=encrypt_phone(f"139000930{name_suffix}"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()
    user = UserAccount(
        phone_enc=encrypt_phone(f"139000931{name_suffix}"),
        name=f"服务商{role}{name_suffix}",
        password_hash=get_password_hash("Pm@12345678"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role=role,
            provider_id=provider.id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": None,
            "role": role,
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}, provider.id


# ── D1：物业 PATCH 内勤率 ────────────────────────────────────────────


@pytest.mark.anyio
async def test_d1_property_patch_internal_rate(
    client, db_session, seeded_tenant, admin_auth_headers
):
    project = _project(db_session, seeded_tenant.id, "D1 项目")
    resp = await client.patch(
        f"/api/v1/admin/projects/{project.id}",
        json={"internal_agent_commission_rate": "0.0700"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(str(resp.json()["internal_agent_commission_rate"])) == Decimal("0.0700")
    db_session.refresh(project)
    assert project.internal_agent_commission_rate == Decimal("0.0700")


@pytest.mark.anyio
async def test_d1_property_patch_cannot_set_provider_rate(
    client, db_session, seeded_tenant, admin_auth_headers
):
    """provider_agent_commission_rate 不在 ProjectUpdateIn — 物业 PATCH 传入被忽略。"""
    project = _project(db_session, seeded_tenant.id, "D1 越权项目")
    resp = await client.patch(
        f"/api/v1/admin/projects/{project.id}",
        json={"provider_agent_commission_rate": "0.9900"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(project)
    assert project.provider_agent_commission_rate is None


# ── D2：服务商 PATCH 服务商率 ────────────────────────────────────────


@pytest.mark.anyio
async def test_d2_provider_patch_provider_rate(client, db_session, seeded_tenant):
    headers, provider_id = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="01")
    project = _project(db_session, seeded_tenant.id, "D2 项目", provider_id=provider_id)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.1300"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(project)
    assert project.provider_agent_commission_rate == Decimal("0.1300")


@pytest.mark.anyio
async def test_d2_cross_provider_404(client, db_session, seeded_tenant):
    headers_a, _provider_a = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="02")
    _headers_b, provider_b = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="03")
    # 项目属服务商 B，调用方是服务商 A
    project_b = _project(db_session, seeded_tenant.id, "B 的项目", provider_id=provider_b)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project_b.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.anyio
async def test_d2_property_side_token_403(
    client, db_session, seeded_tenant, admin_auth_headers
):
    project = _project(db_session, seeded_tenant.id, "D2 物业越权项目")
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.anyio
async def test_d2_provider_agent_role_403(client, db_session, seeded_tenant):
    headers, provider_id = _provider_pm_headers(
        db_session, seeded_tenant.id, name_suffix="04", role="agent"
    )
    project = _project(db_session, seeded_tenant.id, "D2 角色越权项目", provider_id=provider_id)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3.12 -m pytest tests/api/test_project_commission_rates.py -v`
Expected: FAIL — D1：`ProjectOut` 无 `internal_agent_commission_rate` 键 / 字段不落库；D2：`PATCH /provider/projects/{id}/commission-rate` 路由不存在（404 全部命中，含 role/cross-provider 用例假阳性）。

- [ ] **Step 3: `schemas/project.py` 加字段**

In `poc/backend/app/schemas/project.py`:

`ProjectCreateIn` —— 在末尾（`late_fee_waive_disabled` 之后）追加：
```python
    # §9.2-D1 — 项目级内勤催收员佣金率（NULL 继承系统默认 0.05）
    internal_agent_commission_rate: Decimal | None = Field(None, ge=0, le=1)
```

`ProjectUpdateIn` —— 在末尾（`late_fee_waive_disabled` 之后）追加同一行：
```python
    # §9.2-D1 — 项目级内勤催收员佣金率
    internal_agent_commission_rate: Decimal | None = Field(None, ge=0, le=1)
```

`ProjectOut` —— 在末尾（`late_fee_waive_disabled` 之后）追加（两个率都透出）：
```python
    # §9.2 D1/D2 — 项目级佣金率（NULL 表示继承系统默认 0.05）
    internal_agent_commission_rate: Decimal | None = None
    provider_agent_commission_rate: Decimal | None = None
```

> D2 字段**不进** `ProjectUpdateIn` —— 物业 admin 的 PATCH 碰不到它（Pydantic 默认忽略额外字段，对应 `test_d1_property_patch_cannot_set_provider_rate`）。

- [ ] **Step 4: `create_project` 构造器加 D1 字段**

In `poc/backend/app/api/admin_projects.py`, the `Project(...)` constructor in `create_project` — 在 `late_fee_waive_disabled=body.late_fee_waive_disabled,` 之后追加：
```python
        # §9.2-D1 — 项目级内勤佣金率
        internal_agent_commission_rate=body.internal_agent_commission_rate,
```

> `update_project` 的 PATCH 走 `model_dump(exclude_unset=True)` + `setattr` 循环，新字段自动覆盖，无需改端点逻辑。

- [ ] **Step 5: 新增 D2 入参 schema**

In `poc/backend/app/schemas/provider_admin.py`, after `ProviderMemberCommission`, add:

```python
class ProjectCommissionRateIn(BaseModel):
    """§9.2-D2 — 服务商设置本家项目的服务商催收员佣金率。"""

    provider_agent_commission_rate: Decimal = Field(ge=0, le=1)
```

- [ ] **Step 6: 新增 D2 写端点**

In `poc/backend/app/api/provider_admin.py`:

import 处（`from app.schemas.provider_admin import (...)` 块）加入 `ProjectCommissionRateIn`。

在文件末尾、`assign_provider_pm` 之后，追加：

```python
@router.patch("/projects/{project_id}/commission-rate")
async def set_project_commission_rate(
    project_id: int,
    body: ProjectCommissionRateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[
        object, Depends(require_provider_roles("project_manager", "admin"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """§9.2-D2 — 服务商 PM/admin 设置本家项目的服务商催收员佣金率。"""
    from app.models.case import Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.provider_id == provider_id,
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在或不属本服务商"},
        )

    project.provider_agent_commission_rate = body.provider_agent_commission_rate
    db.commit()
    return {
        "status": "ok",
        "project_id": project.id,
        "provider_agent_commission_rate": str(body.provider_agent_commission_rate),
    }
```

- [ ] **Step 7: 跑测试确认通过**

Run: `python3.12 -m pytest tests/api/test_project_commission_rates.py -v`
Expected: PASS（6 passed）。

- [ ] **Step 8: 跑 project 相关回归**

Run: `python3.12 -m pytest tests/api/ -k project -q`
Expected: 全绿。

- [ ] **Step 9: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/project.py poc/backend/app/api/admin_projects.py poc/backend/app/schemas/provider_admin.py poc/backend/app/api/provider_admin.py poc/backend/tests/api/test_project_commission_rates.py
git commit -m "feat(§9.2-D1/D2): 项目级佣金率写端点 — 物业改内勤率/服务商改服务商率"
```

---

## Task 8: 文档标注 + 全量回归 + lint

**Files:**
- Modify: `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md:182`（§9.2 节末尾）

- [ ] **Step 1: 标注角色模型 spec §9.2 已实现**

In `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md`, §9.2「减免归属」节，在 `- 减免额度机制、审批流、佣金算法均为后续独立需求。`（line 182）之后追加一行（对齐 §9.1 / §9.3 的 ✅ 写法）：

```markdown
- ✅ **已实现(2026-05-17)**：`DiscountOffer` 加 `provider_id` 归属；减免 approve/reject/escalate 收紧为物业侧专属(`require_tenant_roles`)；两处佣金（内勤 `admin.py` / 服务商 `provider_admin.py`）改为逐案「实收金额(扣已执行减免)×项目级佣金率」；项目级内勤/服务商佣金率各由物业/服务商在本侧端点配置。详见 `docs/superpowers/specs/2026-05-16-discount-attribution-commission-design.md`。
```

- [ ] **Step 2: 后端全量回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: 全绿（§9.1 后基线 709 测试 + 本计划新增用例，无 fail / error）。

- [ ] **Step 3: lint**

Run: `cd poc/backend && python3.12 -m ruff check . && python3.12 -m ruff format --check .`
Expected: `All checks passed!` —— 若 isort（`I001`）报新 import 顺序，跑 `python3.12 -m ruff check --fix .` 后重跑确认。

- [ ] **Step 4: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-16-role-model-refactor-design.md
git commit -m "docs(§9.2): 角色模型 spec 标注减免归属/审批/佣金已实现"
```

---

## Self-Review

**1. Spec coverage（逐 spec 章节核对）：**
- §3 Part A 减免归属 → Task 1（模型/迁移列）+ Task 2（create 写入 + 透出）✅
- §4 Part B 审批物业侧强制 → Task 3（三端点守卫 `require_tenant_roles`）✅
- §5 Part C 佣金不计减免 → Task 4（`executed_discount_amounts`）+ Task 5/6（调用）✅
- §5.2 佣金率解析 → Task 4（`internal_agent_rate`/`provider_agent_rate`/`DEFAULT_COMMISSION_RATE`）✅
- §6 D1/D2 模型 → Task 1（`Project` 两列）；D1 写 → Task 7（schema + create 构造器 + 复用 PATCH）；D2 写 → Task 7（`ProjectCommissionRateIn` + 新端点）；§6.4 透出 → Task 7（`ProjectOut` 两字段）✅
- §7 两处佣金计算改造 → Task 5（内勤）+ Task 6（服务商，含 `CommissionLineItem.commission_rate`）✅
- §8 迁移 → Task 1（`24018v220d` / down `24017v220c`）✅
- §10 测试清单 → Part A/B/C/D1/D2/佣金计算各项均有对应 task 用例 ✅
- §11 文件清单 → 全部 12 个文件分布于 8 个 task ✅

**2. Placeholder scan：** 无 TBD / TODO / “类似 Task N” —— 每个改动步骤均给出完整代码或精确替换位置。

**3. Type consistency：**
- 服务模块函数名 `executed_discount_amounts` / `internal_agent_rate` / `provider_agent_rate` 在 Task 4 定义、Task 5/6 调用一致。
- `DEFAULT_COMMISSION_RATE`：服务模块为 `Decimal("0.05")`；`provider_admin.py` 既有模块级 float `0.05` 仅用于 base==0 兜底（Task 6），`admin.py` 同类兜底用既有 `INTERNAL_AGENT_COMMISSION_RATE` float（Task 5）—— 两处兜底都赋给 `commission_rate: float` 字段，类型自洽。
- `CommissionLineItem.commission_rate: Decimal`（Task 6）与端点传入的 `provider_agent_rate(...)` 返回 `Decimal` 一致。
- 迁移 revision `24018v220d` / down_revision `24017v220c` 与 Task 1 一致。

**4. 已知范围注记（非缺口）：** `get_agent_commission_detail`、`provider_admin` 账单汇总仍按旧 `amount_owed × 0.05` —— spec §7 明确只点名两个列表端点，detail/汇总不在 §9.2 范围（与 D3 一同归后续）。`DiscountOffer` 重复申请的 TOCTOU 竞态为既有问题，§9.2 不引入也不修复。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-17-discount-attribution-commission.md`. Two execution options:

1. **Subagent-Driven (recommended)** — 每个 task 派新 subagent，task 间两段式 review（spec 合规 → 代码质量），快速迭代。
2. **Inline Execution** — 本会话内按 `executing-plans` 分批执行，批次间设检查点。

Which approach?
