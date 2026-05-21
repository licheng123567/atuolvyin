# 缴费链接 + 收款配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让物业管理单位按项目配置收款信息，催收人员一键发送业主专属缴费二维码/短链，业主扫码看到「应缴 − 已减免 = 应支付」的 H5 静态账单页。

**Architecture:** 项目级收款配置（`Project` 新增 5 字段）+ `payment_link` token 持久化表；共享 `compute_payable` helper 实时读取已审批 `DiscountOffer` 算应付额；坐席/管理端发送端点返回支付明细；新增无鉴权公开端点 + SPA 公开页 `/pay/:token` 渲染业主账单。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL（后端）；React + Refine.dev v5 + qrcode.react（前端）；pytest + Vitest（测试）。

**Spec:** `docs/superpowers/specs/2026-05-19-payment-link-collection-design.md`

**前置说明：** v2.2 Item 2 已落地 `app/services/payment_link.py`（`PaymentLinkOut` + `build_and_record_payment_link`）、`app/api/admin_cases.py` / `app/api/agent_cases.py` 的 `send-payment-link` 端点、`frontend/src/components/admin/PaymentLinkQrModal.tsx`、`frontend/src/pages/admin/cases/detail.tsx` 的发送按钮。本计划在其上扩展。

---

## File Structure

**后端（poc/backend/）**
- `alembic/versions/24022_v220_payment_link.py` — 新建：Project 加 5 字段 + payment_link 建表
- `app/models/case.py` — 修改：`Project` 加 5 个收款字段
- `app/models/payment_link.py` — 新建：`PaymentLink` ORM 模型
- `app/models/__init__.py` — 修改：导出 `PaymentLink`（测试建表需要）
- `app/services/payment_link.py` — 修改：加 `PaymentBreakdown` + `compute_payable`，重构 `build_and_record_payment_link`
- `app/schemas/project.py` — 修改：`ProjectCreateIn` / `ProjectUpdateIn` / `ProjectOut` 加收款字段
- `app/api/admin_projects.py` — 修改：创建/更新写入收款字段
- `app/api/public_payment.py` — 新建：`GET /public/payment/{token}` 无鉴权端点
- `app/main.py` — 修改：注册 public_payment 路由

**前端（frontend/）**
- `src/pages/admin/projects/new.tsx` + `edit.tsx` — 修改：加「收款信息」分组
- `src/components/admin/PaymentLinkQrModal.tsx` — 修改：展示明细构成 + has_pending 提醒
- `src/pages/admin/cases/detail.tsx` — 修改：发送响应改传 token/breakdown/has_pending
- `src/pages/public/PaymentBillPage.tsx` — 新建：业主 H5 账单页
- `src/App.tsx` — 修改：注册公开路由 `/pay/:token`

---

## Task 1: Project 收款字段 + payment_link 模型 + 迁移

**Files:**
- Modify: `poc/backend/app/models/case.py:84`（`Project` 类内，`provider_agent_commission_rate` 之后）
- Create: `poc/backend/app/models/payment_link.py`
- Modify: `poc/backend/app/models/__init__.py`
- Create: `poc/backend/alembic/versions/24022_v220_payment_link.py`
- Test: `poc/backend/tests/api/test_payment_link.py`（沿用现有文件，补 1 个建表冒烟测试）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_payment_link.py` 末尾追加：

```python
def test_payment_link_model_and_project_fields(db_session, seeded_tenant, seeded_case):
    """PaymentLink 表可写入；Project 新增收款字段可读写。"""
    from datetime import UTC, datetime, timedelta

    from app.models.case import Project
    from app.models.payment_link import PaymentLink

    project = Project(tenant_id=seeded_tenant.id, name="收款配置项目")
    project.payee_name = "测试物业管理有限公司"
    project.payee_account = "工行 6222 0000 0000 1234"
    project.payment_instructions = "请到物业服务中心缴费，转账请注明房号"
    db_session.add(project)
    db_session.flush()
    assert project.payment_mode == "property_self"  # server_default

    link = PaymentLink(
        token="tok_test_123456",
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        project_id=project.id,
        payment_mode="property_self",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(link)
    db_session.flush()
    assert link.id is not None
    assert link.created_at is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_payment_link.py::test_payment_link_model_and_project_fields -v`
Expected: FAIL — `ImportError: cannot import name 'PaymentLink'` 或 `AttributeError: payment_mode`。

- [ ] **Step 3: Project 加收款字段**

`poc/backend/app/models/case.py` — 在 `Project` 类 `provider_agent_commission_rate` 字段（第 84 行）之后、`__table_args__` 之前插入：

```python
    # v2.2 — 项目级收款配置（按项目设置；物业管理员在项目编辑页配）
    payment_mode: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="property_self"
    )  # property_self（物业自收，MVP）/ notary_escrow（公证提存，v1.1）
    payee_name: Mapped[str | None] = mapped_column(sa.Text)  # 收款户名
    payee_account: Mapped[str | None] = mapped_column(sa.Text)  # 收款账户（自由文本）
    payee_qr_object_key: Mapped[str | None] = mapped_column(sa.Text)  # 收款码图 MinIO key
    payment_instructions: Mapped[str | None] = mapped_column(sa.Text)  # 线下缴费说明
```

并在 `Project.__table_args__` 元组末尾（最后一个 `CheckConstraint` 之后）加：

```python
        sa.CheckConstraint(
            "payment_mode IN ('property_self','notary_escrow')",
            name="ck_project_payment_mode",
        ),
```

- [ ] **Step 4: 新建 PaymentLink 模型**

Create `poc/backend/app/models/payment_link.py`:

```python
"""v2.2 — 缴费链接 token 持久化（业主 H5 账单页凭 token 查案件）。"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PaymentLink(Base, TimestampMixin):
    __tablename__ = "payment_link"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, unique=True, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("project.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    payment_mode: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="property_self"
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
```

- [ ] **Step 5: 注册模型到 __init__.py**

`poc/backend/app/models/__init__.py` — 在 `from .notification import ...` 一行之后加（保持按字母序的现有风格即可）：

```python
from .payment_link import PaymentLink  # noqa: F401
```

- [ ] **Step 6: 写 Alembic 迁移**

Create `poc/backend/alembic/versions/24022_v220_payment_link.py`:

```python
"""缴费链接 — Project 收款字段 + payment_link 表

Revision ID: 24022v220h
Revises: 24021v220g
Create Date: 2026-05-19 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24022v220h"
down_revision: str | None = "24021v220g"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "payment_mode",
            sa.String(length=16),
            nullable=False,
            server_default="property_self",
        ),
    )
    op.add_column("project", sa.Column("payee_name", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payee_account", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payee_qr_object_key", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payment_instructions", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_project_payment_mode",
        "project",
        "payment_mode IN ('property_self','notary_escrow')",
    )
    op.create_table(
        "payment_link",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "payment_mode",
            sa.String(length=16),
            nullable=False,
            server_default="property_self",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["collection_case.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user_account.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_payment_link_token"),
    )
    op.create_index("ix_payment_link_case", "payment_link", ["case_id"])
    op.create_index("ix_payment_link_tenant", "payment_link", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("payment_link")
    op.drop_constraint("ck_project_payment_mode", "project", type_="check")
    op.drop_column("project", "payment_instructions")
    op.drop_column("project", "payee_qr_object_key")
    op.drop_column("project", "payee_account")
    op.drop_column("project", "payee_name")
    op.drop_column("project", "payment_mode")
```

- [ ] **Step 7: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_payment_link.py::test_payment_link_model_and_project_fields -v`
Expected: PASS（测试用 `Base.metadata.create_all`，无需手动跑迁移）。

- [ ] **Step 8: 校验迁移链 + lint**

Run: `cd poc/backend && python3.12 -m alembic heads && python3.12 -m ruff check app/models/payment_link.py app/models/case.py alembic/versions/24022_v220_payment_link.py`
Expected: `alembic heads` 输出 `24022v220h (head)`；ruff `All checks passed!`。

- [ ] **Step 9: Commit**

```bash
git add poc/backend/app/models/payment_link.py poc/backend/app/models/case.py poc/backend/app/models/__init__.py poc/backend/alembic/versions/24022_v220_payment_link.py poc/backend/tests/api/test_payment_link.py
git commit -m "feat(payment): Project 收款字段 + payment_link 模型与迁移"
```

---

## Task 2: compute_payable —— 减免读取 helper

**Files:**
- Modify: `poc/backend/app/services/payment_link.py`
- Test: `poc/backend/tests/services/test_compute_payable.py`（新建）

`DiscountOffer`（`app/models/discount_offer.py`）字段：`case_id`、`original_amount`、`proposed_amount`、`status`（`pending_supervisor`/`pending_admin`/`approved`/`rejected`/`executed`/`expired`）、`approved_at`、`expires_at`。

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/services/test_compute_payable.py`:

```python
"""v2.2 — compute_payable：案件应付额 = 应缴 − 已审批减免。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _discount_offer(db_session, case, *, status, original, proposed, approved_days_ago=0):
    from app.models.discount_offer import DiscountOffer

    now = datetime.now(UTC)
    offer = DiscountOffer(
        tenant_id=case.tenant_id,
        case_id=case.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal(original),
        proposed_amount=Decimal(proposed),
        discount_pct=10,
        reason="测试减免",
        status=status,
        approver_role_required="supervisor",
        approved_at=now - timedelta(days=approved_days_ago) if status == "approved" else None,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def test_no_discount_payable_equals_owed(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    b = compute_payable(db_session, seeded_case)
    assert b.original == seeded_case.amount_owed
    assert b.waived == Decimal("0")
    assert b.payable == seeded_case.amount_owed
    assert b.has_pending is False


def test_approved_discount_reduces_payable(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    _discount_offer(
        db_session, seeded_case, status="approved",
        original="3000.00", proposed="2400.00",
    )
    b = compute_payable(db_session, seeded_case)
    assert b.payable == Decimal("2400.00")
    assert b.waived == seeded_case.amount_owed - Decimal("2400.00")


def test_pending_discount_does_not_reduce_but_flags(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    _discount_offer(
        db_session, seeded_case, status="pending_supervisor",
        original="3000.00", proposed="2400.00",
    )
    b = compute_payable(db_session, seeded_case)
    assert b.payable == seeded_case.amount_owed  # pending 不抵扣
    assert b.has_pending is True


def test_expired_offer_ignored(db_session, seeded_case):
    from app.models.discount_offer import DiscountOffer
    from app.services.payment_link import compute_payable

    offer = _discount_offer(
        db_session, seeded_case, status="approved",
        original="3000.00", proposed="2000.00",
    )
    offer.expires_at = datetime.now(UTC) - timedelta(days=1)  # 已过期
    db_session.flush()
    b = compute_payable(db_session, seeded_case)
    assert b.payable == seeded_case.amount_owed  # 过期减免不计
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_compute_payable.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_payable'`。

- [ ] **Step 3: 实现 PaymentBreakdown + compute_payable**

`poc/backend/app/services/payment_link.py` — 在 `class PaymentLinkOut` 之前插入：

```python
class PaymentBreakdown(BaseModel):
    """业主缴费明细构成：应缴 − 已减免 = 应支付。"""

    principal: Decimal | None
    late_fee: Decimal | None
    original: Decimal
    waived: Decimal
    payable: Decimal
    has_pending: bool


def compute_payable(db: Session, case: CollectionCase) -> PaymentBreakdown:
    """算案件当前应付额。

    已减免 = 该案件 status='approved' 且未过期的 DiscountOffer（多条取 approved_at 最新）。
    pending 减免不抵扣，但置 has_pending=True 供前端提示。
    """
    from app.models.discount_offer import DiscountOffer

    original = case.amount_owed or Decimal("0")
    now = datetime.now(UTC)

    active_offer = (
        db.execute(
            select(DiscountOffer)
            .where(
                DiscountOffer.case_id == case.id,
                DiscountOffer.status == "approved",
                DiscountOffer.expires_at > now,
            )
            .order_by(DiscountOffer.approved_at.desc())
        )
        .scalars()
        .first()
    )
    if active_offer is not None:
        payable = active_offer.proposed_amount
        waived = original - payable
    else:
        payable = original
        waived = Decimal("0")

    has_pending = (
        db.execute(
            select(DiscountOffer.id).where(
                DiscountOffer.case_id == case.id,
                DiscountOffer.status.in_(("pending_supervisor", "pending_admin")),
            )
        ).first()
        is not None
    )

    return PaymentBreakdown(
        principal=case.principal_amount,
        late_fee=case.late_fee_amount,
        original=original,
        waived=waived,
        payable=payable,
        has_pending=has_pending,
    )
```

在 `payment_link.py` 顶部 import 区补充（`from decimal import Decimal` 已存在则跳过；`select` 来自 sqlalchemy）：

```python
from decimal import Decimal

from sqlalchemy import select
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_compute_payable.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add poc/backend/app/services/payment_link.py poc/backend/tests/services/test_compute_payable.py
git commit -m "feat(payment): compute_payable 读取已审批减免算应付额"
```

---

## Task 3: payment_link 持久化 + 发送端点返回明细

**Files:**
- Modify: `poc/backend/app/services/payment_link.py`（`PaymentLinkOut` + `build_and_record_payment_link`）
- Test: `poc/backend/tests/api/test_payment_link.py`（沿用，补 token 持久化 + breakdown 断言）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_payment_link.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_send_payment_link_persists_token_and_returns_breakdown(
    client, db_session, seeded_case, admin_auth_headers
):
    """发送缴费链接：写 payment_link 行 + 响应含 token 与 breakdown。"""
    from app.models.payment_link import PaymentLink

    resp = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/send-payment-link",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token"]
    assert body["breakdown"]["payable"] is not None
    assert body["breakdown"]["has_pending"] is False

    row = (
        db_session.query(PaymentLink)
        .filter(PaymentLink.token == body["token"])
        .one()
    )
    assert row.case_id == seeded_case.id
    assert row.tenant_id == seeded_case.tenant_id
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_payment_link.py::test_send_payment_link_persists_token_and_returns_breakdown -v`
Expected: FAIL — `KeyError: 'token'`（响应无 token 字段）。

- [ ] **Step 3: 扩展 PaymentLinkOut**

`poc/backend/app/services/payment_link.py` — `class PaymentLinkOut` 改为：

```python
class PaymentLinkOut(BaseModel):
    case_id: int
    token: str
    link: str
    short_link: str
    sent_to: str  # masked phone
    sent_at: datetime
    expires_at: datetime
    sms_status: str  # "queued" / "sent" / "skipped"
    breakdown: PaymentBreakdown
```

- [ ] **Step 4: 重构 build_and_record_payment_link**

`poc/backend/app/services/payment_link.py` — `build_and_record_payment_link` 整个函数体替换为：

```python
def build_and_record_payment_link(
    db: Session,
    *,
    case: CollectionCase,
    owner: OwnerProfile,
    actor_user_id: int,
    actor_role: str,
    tenant_id: int,
) -> PaymentLinkOut:
    """生成缴费短链、写 payment_link 行 + audit log，返回链接与支付明细。

    调用方需先完成：案件归属校验 / owner 存在性校验 / 鉴权。
    """
    from app.models.payment_link import PaymentLink

    token = token_urlsafe(12)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=7)
    full_link = f"https://pay.youcuihuicui.com/c/{token}"
    short_link = f"https://yzhc.cn/p/{token[:8]}"
    sent_to_masked = mask_phone(owner.phone_enc)

    db.add(
        PaymentLink(
            token=token,
            tenant_id=tenant_id,
            case_id=case.id,
            project_id=case.project_id,
            created_by_user_id=actor_user_id,
            payment_mode="property_self",
            expires_at=expires_at,
        )
    )

    breakdown = compute_payable(db, case)

    log_audit(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        tenant_id=tenant_id,
        action="case.payment_link_sent",
        target_type="collection_case",
        target_id=case.id,
        payload={
            "owner_phone_masked": sent_to_masked,
            "amount": str(case.amount_owed) if case.amount_owed else None,
            "payable": str(breakdown.payable),
            "token": token,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()

    return PaymentLinkOut(
        case_id=case.id,
        token=token,
        link=full_link,
        short_link=short_link,
        sent_to=sent_to_masked,
        sent_at=now,
        expires_at=expires_at,
        sms_status="queued",
        breakdown=breakdown,
    )
```

> 注：`case.project_id` 是 `CollectionCase` 已有字段（关联项目）。`token_urlsafe`、`timedelta`、`mask_phone` 在文件顶部 import 区已有；若 Task 2 未补全，确认 `from datetime import UTC, datetime, timedelta`、`from secrets import token_urlsafe`、`from app.core.crypto import mask_phone` 都在。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_payment_link.py -v`
Expected: PASS（含原有 6 个 + 新增 1 个 = 7 passed）。

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/services/payment_link.py poc/backend/tests/api/test_payment_link.py
git commit -m "feat(payment): payment_link token 持久化 + 发送响应返回支付明细"
```

---

## Task 4: 项目收款字段 schema + 写入

**Files:**
- Modify: `poc/backend/app/schemas/project.py`（`ProjectCreateIn` / `ProjectUpdateIn` / `ProjectOut`）
- Modify: `poc/backend/app/api/admin_projects.py`（创建写入 + PATCH 写入）
- Test: `poc/backend/tests/api/test_project_commission_rates.py`（沿用，补收款字段往返断言）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_project_commission_rates.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_project_payee_fields_create_and_patch(
    client, db_session, seeded_tenant, admin_auth_headers
):
    """创建项目带收款信息 → 回显；PATCH 可改收款信息。"""
    coordinator_id = _tenant_member(db_session, seeded_tenant.id, "coordinator", "20")
    legal_id = _tenant_member(db_session, seeded_tenant.id, "legal", "21")
    resp = await client.post(
        "/api/v1/admin/projects",
        json={
            "name": "收款配置项目",
            "coordinator_user_id": coordinator_id,
            "legal_user_id": legal_id,
            "payee_name": "金桂物业管理有限公司",
            "payee_account": "工行 6222 0000 1234",
            "payment_instructions": "工作日 9-17 点到服务中心缴费",
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]
    assert resp.json()["payee_name"] == "金桂物业管理有限公司"
    assert resp.json()["payment_mode"] == "property_self"

    patch = await client.patch(
        f"/api/v1/admin/projects/{project_id}",
        json={"payee_account": "建行 6217 9999 8888"},
        headers=admin_auth_headers,
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["payee_account"] == "建行 6217 9999 8888"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_project_commission_rates.py::test_project_payee_fields_create_and_patch -v`
Expected: FAIL — 响应无 `payee_name`（schema 未含该字段，被忽略）。

- [ ] **Step 3: schema 加收款字段**

`poc/backend/app/schemas/project.py` — `ProjectCreateIn` 末尾（`provider_agent_commission_rate` 之后）加：

```python
    # v2.2 — 项目级收款配置（物业自收模式）
    payee_name: str | None = Field(None, max_length=200)
    payee_account: str | None = Field(None, max_length=500)
    payee_qr_object_key: str | None = Field(None, max_length=500)
    payment_instructions: str | None = Field(None, max_length=2000)
```

`ProjectUpdateIn` 末尾（`internal_agent_commission_rate` 之后）加同样 4 行。

`ProjectOut` 末尾（`provider_agent_commission_rate` 之后）加：

```python
    # v2.2 — 项目级收款配置
    payment_mode: str = "property_self"
    payee_name: str | None = None
    payee_account: str | None = None
    payee_qr_object_key: str | None = None
    payment_instructions: str | None = None
```

- [ ] **Step 4: 创建端点写入收款字段**

`poc/backend/app/api/admin_projects.py` — 创建逻辑里 `Project(...)` 构造（`provider_agent_commission_rate=body.provider_agent_commission_rate,` 之后）加：

```python
        # v2.2 — 项目级收款配置
        payee_name=body.payee_name,
        payee_account=body.payee_account,
        payee_qr_object_key=body.payee_qr_object_key,
        payment_instructions=body.payment_instructions,
```

- [ ] **Step 5: PATCH 端点写入收款字段**

`poc/backend/app/api/admin_projects.py` 的 PATCH 端点（`update_project`，约 390-420 行）用 `body.model_dump(exclude_unset=True)` 套字段。确认 PATCH 把入参字段写回 `Project`：找到将 `data` 写入 `p` 的循环（形如 `for k, v in data.items(): setattr(p, k, v)`），收款字段已随 `ProjectUpdateIn` 自动覆盖，无需额外代码。若 PATCH 是逐字段显式赋值（非循环），则在其中补上述 4 个字段的赋值。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_project_commission_rates.py -v`
Expected: PASS（原有 8 + 新增 1 = 9 passed）。

- [ ] **Step 7: Commit**

```bash
git add poc/backend/app/schemas/project.py poc/backend/app/api/admin_projects.py poc/backend/tests/api/test_project_commission_rates.py
git commit -m "feat(payment): 项目收款配置字段 schema 与读写"
```

---

## Task 5: 业主公开端点 GET /public/payment/{token}

**Files:**
- Create: `poc/backend/app/api/public_payment.py`
- Modify: `poc/backend/app/main.py`（注册路由）
- Test: `poc/backend/tests/api/test_public_payment.py`（新建）

- [ ] **Step 1: 写失败测试**

Create `poc/backend/tests/api/test_public_payment.py`:

```python
"""v2.2 — 业主公开缴费页端点 GET /public/payment/{token}。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


async def _send_link(client, case_id, headers) -> str:
    resp = await client.post(
        f"/api/v1/admin/cases/{case_id}/send-payment-link", headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


@pytest.mark.asyncio
async def test_public_payment_returns_bill(
    client, db_session, seeded_case, admin_auth_headers
):
    """凭有效 token 取账单：含明细、收款信息、业主姓名，不含手机号。"""
    token = await _send_link(client, seeded_case.id, admin_auth_headers)
    resp = await client.get(f"/api/v1/public/payment/{token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["owner_name"] == "张三"
    assert body["breakdown"]["payable"] is not None
    assert body["payment_mode"] == "property_self"
    # 不得泄露手机号
    assert "phone" not in str(body).lower()


@pytest.mark.asyncio
async def test_public_payment_unknown_token_404(client):
    resp = await client.get("/api/v1/public/payment/nonexistent_token")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_payment_expired_token_410(
    client, db_session, seeded_case, admin_auth_headers
):
    from app.models.payment_link import PaymentLink

    token = await _send_link(client, seeded_case.id, admin_auth_headers)
    row = db_session.query(PaymentLink).filter(PaymentLink.token == token).one()
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    resp = await client.get(f"/api/v1/public/payment/{token}")
    assert resp.status_code == 410
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_public_payment.py -v`
Expected: FAIL — 404 路由不存在（所有用例失败）。

- [ ] **Step 3: 实现公开端点**

Create `poc/backend/app/api/public_payment.py`:

```python
"""v2.2 — 业主公开缴费页：无鉴权，凭 token 查案件账单。

不返回业主手机号（PRD §14 防信息泄露）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.storage import storage
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.payment_link import PaymentLink
from app.services.payment_link import PaymentBreakdown, compute_payable

router = APIRouter()


class PublicPaymentOut(BaseModel):
    owner_name: str
    owner_room: str | None
    payment_mode: str
    payee_name: str | None
    payee_account: str | None
    payee_qr_url: str | None
    payment_instructions: str | None
    breakdown: PaymentBreakdown


@router.get("/payment/{token}", response_model=PublicPaymentOut)
def get_public_payment(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> PublicPaymentOut:
    """业主扫码 / 点链接打开账单页（无需登录）。"""
    link = (
        db.query(PaymentLink).filter(PaymentLink.token == token).one_or_none()
    )
    if link is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "缴费链接不存在"},
        )
    if link.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=http_status.HTTP_410_GONE,
            detail={"code": "ERR_LINK_EXPIRED", "message": "缴费链接已失效，请联系物业重新获取"},
        )

    case = db.get(CollectionCase, link.case_id)
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    project = db.get(Project, link.project_id) if link.project_id else None

    qr_url = (
        storage.get_url(project.payee_qr_object_key)
        if project and project.payee_qr_object_key
        else None
    )
    return PublicPaymentOut(
        owner_name=owner.name if owner else "业主",
        owner_room=owner.room if owner else None,
        payment_mode=project.payment_mode if project else "property_self",
        payee_name=project.payee_name if project else None,
        payee_account=project.payee_account if project else None,
        payee_qr_url=qr_url,
        payment_instructions=project.payment_instructions if project else None,
        breakdown=compute_payable(db, case),
    )
```

- [ ] **Step 4: 注册路由**

`poc/backend/app/main.py` — 在 import 区（约 26 行 `agent_cases,` 附近）加 `public_payment,`；在 `include_router` 区末尾（约 336 行 `super_config` 之后）加：

```python
app.include_router(
    public_payment.router, prefix="/api/v1/public", tags=["public-payment"]
)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_public_payment.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/api/public_payment.py poc/backend/app/main.py poc/backend/tests/api/test_public_payment.py
git commit -m "feat(payment): 业主公开缴费页端点 GET /public/payment/{token}"
```

---

## Task 6: 前端项目页 —— 收款信息分组

**Files:**
- Modify: `frontend/src/pages/admin/projects/new.tsx`
- Modify: `frontend/src/pages/admin/projects/edit.tsx`
- Test: `frontend/src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`（沿用，补收款字段断言）

- [ ] **Step 1: 写失败测试**

在 `frontend/src/pages/admin/projects/__tests__/commission-rate-field.test.tsx` 末尾追加：

```tsx
describe("项目创建表单 — 收款信息", () => {
  it("渲染收款户名 / 收款账户 / 缴费说明字段", () => {
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText("例：金桂物业管理有限公司")).toBeDefined();
    expect(screen.getByPlaceholderText(/例：工行/)).toBeDefined();
    expect(screen.getByPlaceholderText(/到物业服务中心/)).toBeDefined();
  });

  it("填收款信息提交 → payload 含 payee_name / payee_account", () => {
    createMutate.mockClear();
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );
    fillRequiredFields();
    fireEvent.change(screen.getByPlaceholderText("例：金桂物业管理有限公司"), {
      target: { value: "金桂物业" },
    });
    fireEvent.change(screen.getByPlaceholderText(/例：工行/), {
      target: { value: "工行 6222 1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    const callArg = createMutate.mock.calls[0][0] as {
      values: { payee_name: string; payee_account: string };
    };
    expect(callArg.values.payee_name).toBe("金桂物业");
    expect(callArg.values.payee_account).toBe("工行 6222 1234");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`
Expected: FAIL — `Unable to find an element by placeholder text 例：金桂物业管理有限公司`。

- [ ] **Step 3: new.tsx 加 state**

`frontend/src/pages/admin/projects/new.tsx` — 在 `providerCommRate` state（约 59 行）之后加：

```tsx
  // v2.2 — 项目收款信息
  const [payeeName, setPayeeName] = useState("");
  const [payeeAccount, setPayeeAccount] = useState("");
  const [paymentInstructions, setPaymentInstructions] = useState("");
```

- [ ] **Step 4: new.tsx submit() 带上收款字段**

`frontend/src/pages/admin/projects/new.tsx` — `submit()` 的 `values` 对象里（`late_fee_waive_disabled` 行之后、`};` 之前）加：

```tsx
      // v2.2 — 项目收款信息
      payee_name: payeeName.trim() || null,
      payee_account: payeeAccount.trim() || null,
      payment_instructions: paymentInstructions.trim() || null,
```

- [ ] **Step 5: new.tsx 加收款信息分组 UI**

`frontend/src/pages/admin/projects/new.tsx` — 在「收费标准 + 合同」分组（`💰 收费标准 + 合同` 那个 `ds-card`/`form-group` 块）之后插入：

```tsx
          {/* v2.2 — 项目收款信息 */}
          <div
            className="form-group"
            style={{
              background: "#f9fafb",
              padding: 12,
              borderRadius: 6,
              border: "1px solid #e5e7eb",
              marginBottom: 16,
            }}
          >
            <div className="setting-label" style={{ marginBottom: 4 }}>
              🏦 收款信息（业主缴费链接展示）
            </div>
            <div className="setting-hint" style={{ marginBottom: 12 }}>
              业主扫描缴费二维码后看到的收款账户与缴费说明，按项目分别配置。
            </div>
            <div className="form-group">
              <label className="form-label">收款户名</label>
              <input
                className="form-control"
                value={payeeName}
                onChange={(e) => setPayeeName(e.target.value)}
                placeholder="例：金桂物业管理有限公司"
              />
            </div>
            <div className="form-group">
              <label className="form-label">收款账户</label>
              <input
                className="form-control"
                value={payeeAccount}
                onChange={(e) => setPayeeAccount(e.target.value)}
                placeholder="例：工行 6222 0000 0000 1234"
              />
            </div>
            <div className="form-group">
              <label className="form-label">缴费说明</label>
              <textarea
                className="form-control"
                value={paymentInstructions}
                onChange={(e) => setPaymentInstructions(e.target.value)}
                placeholder="例：工作日 9:00-17:00 到物业服务中心缴费；银行转账请注明房号"
                style={{ minHeight: 60 }}
              />
            </div>
          </div>
```

- [ ] **Step 6: edit.tsx 同步收款字段**

`frontend/src/pages/admin/projects/edit.tsx` — 镜像 new.tsx：(a) 加 `payeeName` / `payeeAccount` / `paymentInstructions` 三个 state；(b) 在加载项目数据的 `useEffect`（回填 `chargeNotes` 等字段处）补 `setPayeeName(data.payee_name ?? "")`、`setPayeeAccount(data.payee_account ?? "")`、`setPaymentInstructions(data.payment_instructions ?? "")`，并在 `ProjectDetail` 接口加 `payee_name: string | null` / `payee_account: string | null` / `payment_instructions: string | null`；(c) 提交 `values` 加 Step 4 的 3 行；(d) 复制 Step 5 的收款信息分组 UI 到同样位置。

- [ ] **Step 7: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`
Expected: PASS（原有 5 + 新增 2 = 7 passed）。

- [ ] **Step 8: typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出（通过）。

```bash
git add frontend/src/pages/admin/projects/new.tsx frontend/src/pages/admin/projects/edit.tsx frontend/src/pages/admin/projects/__tests__/commission-rate-field.test.tsx
git commit -m "feat(payment): 项目页收款信息配置分组"
```

---

## Task 7: PaymentLinkQrModal 展示明细构成

**Files:**
- Modify: `frontend/src/components/admin/PaymentLinkQrModal.tsx`
- Modify: `frontend/src/pages/admin/cases/detail.tsx`
- Test: `frontend/src/components/admin/__tests__/PaymentLinkQrModal.test.tsx`（沿用，改写为新 props）

- [ ] **Step 1: 改写测试为新 props**

`frontend/src/components/admin/__tests__/PaymentLinkQrModal.test.tsx` 整个文件替换为：

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PaymentLinkQrModal } from "../PaymentLinkQrModal";

const BREAKDOWN = {
  principal: "3000.00",
  late_fee: "200.00",
  original: "3200.00",
  waived: "200.00",
  payable: "3000.00",
  has_pending: false,
};

const PROPS = {
  token: "tok_abc123",
  breakdown: BREAKDOWN,
  sentTo: "138****1234",
  hasPending: false,
  onClose: vi.fn(),
};

describe("PaymentLinkQrModal", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("展示支付明细：应缴 / 已减免 / 应支付", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    expect(screen.getByText(/应缴合计/)).toBeDefined();
    expect(screen.getByText(/已减免/)).toBeDefined();
    expect(screen.getByText(/应支付/)).toBeDefined();
    expect(screen.getByText(/3,?000\.00/)).toBeDefined();
  });

  it("渲染缴费二维码（size=180 的 svg）", () => {
    const { container } = render(<PaymentLinkQrModal {...PROPS} />);
    expect(container.querySelector('svg[width="180"]')).not.toBeNull();
  });

  it("has_pending 为真时显示待审批减免提醒", () => {
    render(<PaymentLinkQrModal {...PROPS} hasPending={true} />);
    expect(screen.getByText(/待审批减免/)).toBeDefined();
  });

  it("has_pending 为假时不显示提醒", () => {
    render(<PaymentLinkQrModal {...PROPS} hasPending={false} />);
    expect(screen.queryByText(/待审批减免/)).toBeNull();
  });

  it("点击复制按钮 → 缴费链接写入剪贴板", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    fireEvent.click(screen.getByText("复制链接"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("/pay/tok_abc123"),
    );
  });

  it("点击完成触发 onClose", () => {
    const onClose = vi.fn();
    render(<PaymentLinkQrModal {...PROPS} onClose={onClose} />);
    fireEvent.click(screen.getByText("完成"));
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/components/admin/__tests__/PaymentLinkQrModal.test.tsx`
Expected: FAIL — 组件仍是旧 props（`link`/`shortLink`），新断言找不到明细文案。

- [ ] **Step 3: 重写 PaymentLinkQrModal**

`frontend/src/components/admin/PaymentLinkQrModal.tsx` 整个文件替换为：

```tsx
// v2.2 — 缴费链接二维码弹窗：展示支付明细构成 + 二维码 / 短链，供微信发给业主
import { Copy, CreditCard, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";

export interface PaymentBreakdown {
  principal: string | null;
  late_fee: string | null;
  original: string;
  waived: string;
  payable: string;
  has_pending: boolean;
}

interface Props {
  token: string;
  breakdown: PaymentBreakdown;
  sentTo?: string;
  hasPending: boolean;
  onClose: () => void;
}

function yuan(v: string | null): string {
  if (v == null) return "—";
  return `¥ ${Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PaymentLinkQrModal({
  token,
  breakdown,
  sentTo,
  hasPending,
  onClose,
}: Props) {
  const [copied, setCopied] = useState(false);
  // 缴费链接 = 当前站点的公开账单页（业主扫码 / 点链接都能打开）
  const shareUrl = `${window.location.origin}/pay/${token}`;

  function copy() {
    void navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const row: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 13,
    padding: "3px 0",
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1000 }}>
      <div
        className="ds-modal"
        style={{ maxWidth: 420 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span className="modal-title">
            <CreditCard
              className="inline w-4 h-4 mr-1"
              style={{ verticalAlign: "-3px" }}
            />
            缴费链接
          </span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div
          className="modal-body"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            alignItems: "center",
          }}
        >
          {sentTo && (
            <div style={{ fontSize: 13, color: "#6b7280", textAlign: "center" }}>
              业主 {sentTo} 的缴费链接已生成
            </div>
          )}

          {hasPending && (
            <div
              style={{
                background: "#fffbeb",
                color: "#92400e",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 12,
                width: "100%",
              }}
            >
              ⚠ 该案件有待审批减免，当前链接金额按已审批结果计算；减免审批通过后业主刷新链接即见更新。
            </div>
          )}

          {/* 支付明细构成 */}
          <div
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "#f9fafb",
              borderRadius: 6,
            }}
          >
            <div style={row}>
              <span style={{ color: "#6b7280" }}>物业费本金</span>
              <span>{yuan(breakdown.principal)}</span>
            </div>
            <div style={row}>
              <span style={{ color: "#6b7280" }}>违约金 / 滞纳金</span>
              <span>{yuan(breakdown.late_fee)}</span>
            </div>
            <div style={{ ...row, borderTop: "1px solid #e5e7eb", marginTop: 2 }}>
              <span style={{ color: "#6b7280" }}>应缴合计</span>
              <span>{yuan(breakdown.original)}</span>
            </div>
            {Number(breakdown.waived) > 0 && (
              <div style={row}>
                <span style={{ color: "#6b7280" }}>已减免</span>
                <span style={{ color: "#16a34a" }}>- {yuan(breakdown.waived)}</span>
              </div>
            )}
            <div
              style={{
                ...row,
                borderTop: "1px solid #e5e7eb",
                marginTop: 2,
                fontWeight: 700,
              }}
            >
              <span>应支付</span>
              <span style={{ color: "var(--color-primary)" }}>
                {yuan(breakdown.payable)}
              </span>
            </div>
          </div>

          <div
            style={{
              background: "#fff",
              padding: 12,
              borderRadius: 8,
              border: "1px solid var(--color-neutral-200)",
            }}
          >
            <QRCodeSVG value={shareUrl} size={180} level="M" />
          </div>
          <div
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              background: "#f9fafb",
              borderRadius: 6,
            }}
          >
            <span
              style={{
                flex: 1,
                fontFamily: "monospace",
                fontSize: 12,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {shareUrl}
            </span>
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={copy}
              style={{ padding: "4px 8px" }}
            >
              <Copy className="w-3 h-3" />
              {copied ? "已复制" : "复制链接"}
            </button>
          </div>
          <div
            style={{
              background: "#eff6ff",
              color: "#1e40af",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 12,
              width: "100%",
              textAlign: "center",
            }}
          >
            催收人员可截图二维码或复制链接，通过微信发给业主缴费
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="ds-btn ds-btn-primary" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: detail.tsx 适配新 props**

`frontend/src/pages/admin/cases/detail.tsx`：

(a) `paymentLink` state 改为携带 token/breakdown/has_pending —— 把原 `useState<{ link; short_link; sent_to } | null>` 改为：

```tsx
  const [paymentLink, setPaymentLink] = useState<{
    token: string;
    breakdown: import("../../../components/admin/PaymentLinkQrModal").PaymentBreakdown;
    sent_to: string;
  } | null>(null);
```

(b) `handleSendPaymentLink` 的 `onSuccess` 改为：

```tsx
        onSuccess: (resp) => {
          const d = resp.data as {
            token: string;
            sent_to: string;
            breakdown: import("../../../components/admin/PaymentLinkQrModal").PaymentBreakdown;
          };
          setPaymentLink({
            token: d.token,
            breakdown: d.breakdown,
            sent_to: d.sent_to,
          });
        },
```

(c) 渲染处改为：

```tsx
      {paymentLink && (
        <PaymentLinkQrModal
          token={paymentLink.token}
          breakdown={paymentLink.breakdown}
          sentTo={paymentLink.sent_to}
          hasPending={paymentLink.breakdown.has_pending}
          onClose={() => setPaymentLink(null)}
        />
      )}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/components/admin/__tests__/PaymentLinkQrModal.test.tsx`
Expected: PASS（6 passed）。

- [ ] **Step 6: typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出。

```bash
git add frontend/src/components/admin/PaymentLinkQrModal.tsx frontend/src/components/admin/__tests__/PaymentLinkQrModal.test.tsx frontend/src/pages/admin/cases/detail.tsx
git commit -m "feat(payment): 缴费弹窗展示支付明细构成 + 待审批减免提醒"
```

---

## Task 8: 业主 H5 账单页 + 公开路由

**Files:**
- Create: `frontend/src/pages/public/PaymentBillPage.tsx`
- Modify: `frontend/src/App.tsx`（公开路由）
- Test: `frontend/src/pages/public/__tests__/PaymentBillPage.test.tsx`（新建）

- [ ] **Step 1: 写失败测试**

Create `frontend/src/pages/public/__tests__/PaymentBillPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PaymentBillPage } from "../PaymentBillPage";

function renderAt(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/pay/${token}`]}>
      <Routes>
        <Route path="/pay/:token" element={<PaymentBillPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PaymentBillPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("加载成功 → 展示业主姓名与应支付金额", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        owner_name: "张三",
        owner_room: "5-203",
        payment_mode: "property_self",
        payee_name: "金桂物业",
        payee_account: "工行 6222 1234",
        payee_qr_url: null,
        payment_instructions: "到服务中心缴费",
        breakdown: {
          principal: "3000.00",
          late_fee: "200.00",
          original: "3200.00",
          waived: "0.00",
          payable: "3200.00",
          has_pending: false,
        },
      }),
    } as Response);

    renderAt("tok_ok");
    await waitFor(() => expect(screen.getByText(/张三/)).toBeDefined());
    expect(screen.getByText(/金桂物业/)).toBeDefined();
    expect(screen.getByText(/3,?200\.00/)).toBeDefined();
  });

  it("链接失效（410）→ 展示失效提示", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 410,
      json: async () => ({ code: "ERR_LINK_EXPIRED", message: "缴费链接已失效" }),
    } as Response);

    renderAt("tok_expired");
    await waitFor(() =>
      expect(screen.getByText(/链接已失效|失效/)).toBeDefined(),
    );
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/public/__tests__/PaymentBillPage.test.tsx`
Expected: FAIL — `Failed to resolve import "../PaymentBillPage"`。

- [ ] **Step 3: 实现 PaymentBillPage**

Create `frontend/src/pages/public/PaymentBillPage.tsx`:

```tsx
// v2.2 — 业主公开缴费账单页（无需登录，凭 token 展示账单）
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

interface Breakdown {
  principal: string | null;
  late_fee: string | null;
  original: string;
  waived: string;
  payable: string;
  has_pending: boolean;
}

interface Bill {
  owner_name: string;
  owner_room: string | null;
  payment_mode: string;
  payee_name: string | null;
  payee_account: string | null;
  payee_qr_url: string | null;
  payment_instructions: string | null;
  breakdown: Breakdown;
}

function yuan(v: string | null): string {
  if (v == null) return "—";
  return `¥ ${Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PaymentBillPage() {
  const { token } = useParams<{ token: string }>();
  const [bill, setBill] = useState<Bill | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE ?? "";
    fetch(`${base}/api/v1/public/payment/${token}`)
      .then(async (resp) => {
        if (resp.status === 410) {
          setError("缴费链接已失效，请联系物业重新获取");
          return;
        }
        if (!resp.ok) {
          setError("缴费链接无效，请联系物业核对");
          return;
        }
        setBill((await resp.json()) as Bill);
      })
      .catch(() => setError("加载失败，请检查网络后重试"))
      .finally(() => setLoading(false));
  }, [token]);

  const wrap: React.CSSProperties = {
    maxWidth: 420,
    margin: "0 auto",
    padding: 16,
    fontFamily: "system-ui, sans-serif",
  };

  if (loading) {
    return <div style={{ ...wrap, textAlign: "center", color: "#6b7280" }}>加载中…</div>;
  }
  if (error || !bill) {
    return (
      <div style={{ ...wrap, textAlign: "center", color: "#b91c1c", paddingTop: 80 }}>
        {error ?? "缴费信息不存在"}
      </div>
    );
  }

  const row: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    padding: "4px 0",
    fontSize: 14,
  };

  return (
    <div style={wrap}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
        {bill.payee_name ?? "物业缴费"}
      </h2>
      <div style={{ color: "#6b7280", fontSize: 14, marginBottom: 16 }}>
        您好，{bill.owner_name}
        {bill.owner_room ? `，房号 ${bill.owner_room}` : ""}
      </div>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 14,
          marginBottom: 16,
        }}
      >
        <div style={row}>
          <span style={{ color: "#6b7280" }}>物业费本金</span>
          <span>{yuan(bill.breakdown.principal)}</span>
        </div>
        <div style={row}>
          <span style={{ color: "#6b7280" }}>违约金 / 滞纳金</span>
          <span>{yuan(bill.breakdown.late_fee)}</span>
        </div>
        <div style={{ ...row, borderTop: "1px solid #e5e7eb" }}>
          <span style={{ color: "#6b7280" }}>应缴合计</span>
          <span>{yuan(bill.breakdown.original)}</span>
        </div>
        {Number(bill.breakdown.waived) > 0 && (
          <div style={row}>
            <span style={{ color: "#6b7280" }}>已减免</span>
            <span style={{ color: "#16a34a" }}>- {yuan(bill.breakdown.waived)}</span>
          </div>
        )}
        <div
          style={{
            ...row,
            borderTop: "1px solid #e5e7eb",
            fontWeight: 700,
            fontSize: 16,
          }}
        >
          <span>应支付</span>
          <span style={{ color: "#2563eb" }}>{yuan(bill.breakdown.payable)}</span>
        </div>
      </div>

      <div style={{ fontSize: 14, lineHeight: 1.7 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>缴费方式</div>
        {bill.payment_instructions && (
          <div style={{ whiteSpace: "pre-wrap", color: "#374151" }}>
            {bill.payment_instructions}
          </div>
        )}
        {bill.payee_account && (
          <div style={{ color: "#374151" }}>收款账户：{bill.payee_account}</div>
        )}
        {bill.payee_name && (
          <div style={{ color: "#374151" }}>收款户名：{bill.payee_name}</div>
        )}
        {bill.payee_qr_url && (
          <img
            src={bill.payee_qr_url}
            alt="收款码"
            style={{ width: 180, marginTop: 8 }}
          />
        )}
      </div>

      <div
        style={{
          marginTop: 20,
          paddingTop: 12,
          borderTop: "1px dashed #e5e7eb",
          fontSize: 12,
          color: "#9ca3af",
          textAlign: "center",
        }}
      >
        —— v1.1 上线后可在此直接扫码支付 ——
      </div>
    </div>
  );
}
```

- [ ] **Step 4: App.tsx 注册公开路由**

`frontend/src/App.tsx`：(a) 顶部 import 区加 `import { PaymentBillPage } from "./pages/public/PaymentBillPage";`；(b) 在 `{/* Public */}` 注释下、`/help/app` 路由之后加：

```tsx
          <Route path="/pay/:token" element={<PaymentBillPage />} />
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/public/__tests__/PaymentBillPage.test.tsx`
Expected: PASS（2 passed）。

- [ ] **Step 6: typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无输出。

```bash
git add frontend/src/pages/public/PaymentBillPage.tsx frontend/src/App.tsx frontend/src/pages/public/__tests__/PaymentBillPage.test.tsx
git commit -m "feat(payment): 业主 H5 缴费账单页 + 公开路由 /pay/:token"
```

---

## 收尾验证

- [ ] **后端全量回归**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_payment_link.py tests/api/test_public_payment.py tests/services/test_compute_payable.py tests/api/test_project_commission_rates.py tests/api/test_admin_cases_actions.py tests/api/test_agent_cases.py -q`
Expected: 全部 PASS。

- [ ] **后端 lint**

Run: `cd poc/backend && python3.12 -m ruff check app/ tests/`
Expected: `All checks passed!`

- [ ] **前端构建 + 全量测试**

Run: `cd frontend && npm run build && npx vitest run`
Expected: 构建无 TS 报错；全部测试 PASS。

- [ ] **E2E 冒烟**

Run: `cd frontend && npx playwright test e2e/per-role-pages.spec.ts --project=chromium`
Expected: 30 passed（确认 admin 案件/项目页无 runtime error）。

- [ ] **人工验收**（物业管理员 `13000000002` / `Demo@123!`）
  - 新建/编辑项目 → 填收款户名/账户/缴费说明 → 保存回显
  - 案件详情 → 「发送缴费链接」→ 弹窗显示「应缴 − 已减免 = 应支付」明细 + 二维码
  - 对有待审批减免的案件发送 → 弹窗顶部出现待审批提醒条
  - 浏览器打开弹窗里的链接 `/pay/{token}` → H5 账单页正常渲染；手动改 `payment_link.expires_at` 为过期 → 页面显示「链接已失效」

---

## Self-Review

**Spec 覆盖检查：**
- §3 项目级收款配置 → Task 1（模型）+ Task 4（schema/API）+ Task 6（前端）✓
- §4 payment_link 持久化 → Task 1（表）+ Task 3（写入）✓
- §5 支付明细构成 + 减免联动 → Task 2（compute_payable）✓
- §5.5 待审批减免非阻断提醒 → Task 2（has_pending）+ Task 7（提醒条）✓
- §6.1 发送端点返回 breakdown → Task 3 ✓
- §6.2 公开端点 → Task 5 ✓
- §7.1 项目页收款配置 → Task 6 ✓
- §7.2 弹窗明细 → Task 7 ✓
- §7.3 H5 账单页 → Task 8 ✓
- §9 公证提存（v1.1）→ 不在本计划，`payment_mode` 字段已预留 ✓

**类型一致性：** `PaymentBreakdown`（后端 Pydantic / 前端 TS interface）字段 `principal/late_fee/original/waived/payable/has_pending` 全程一致；`PaymentLinkOut.token` 在 Task 3 定义、Task 7 前端消费一致；Decimal 经 JSON 序列化为字符串，前端 interface 用 `string`，`yuan()` 用 `Number()` 转换 —— 一致。

**无占位符：** 所有步骤含完整代码与确切命令。
