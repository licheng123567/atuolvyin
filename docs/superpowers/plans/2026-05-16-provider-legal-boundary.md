# §9.1 服务商法务职责边界 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让服务商侧法务用户（`role='legal'` 且 `provider_id` 非空）能只读浏览本服务商项目下的案件、上传补充材料、发起法务转化请求、跟进进度，其余法务能力仍物业专属。

**Architecture:** 新建 `app/api/provider_legal.py` 路由，整路由用 `require_provider_roles("legal")` 守卫；案件/请求归属经 `CollectionCase.project_id → Project.provider_id` 推导；补充材料存进新表 `legal_conversion_request_material`。物业侧补 2 个端点让审批人看材料。物业侧既有 legal 端点完全不动。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + MinIO/LocalFileStorage；pytest + testcontainers-postgres + starlette `TestClient`。

**设计文档：** `docs/superpowers/specs/2026-05-16-provider-legal-boundary-design.md`

**前置事实（实现者必读）：**
- 仓库根 `/Users/shuo/AI/autoluyin`，后端 `poc/backend/`，所有 `pytest` / `alembic` 命令在 `poc/backend/` 下执行。
- 测试用 `python3.12 -m pytest`（testcontainers 需宿主 docker daemon）。
- pytest 配置 `asyncio_mode = "auto"` —— `async def test_` 无需装饰器；同步 `def test_` 也可。
- 测试 DB 由 `tests/conftest.py` 的 `Base.metadata.create_all(engine)` 建表（ORM 元数据），**不跑 migration** —— 新 ORM 模型加进已被导入的 `app/models/legal_conversion.py` 即会自动建表。
- 错误响应统一 `{"code": "ERR_XXX", "message": "..."}`；API 前缀 `/api/v1/`。
- 鉴权守卫在 `app/core/security.py`：`require_provider_roles(*roles)` 断言角色匹配 + `provider_id IS NOT NULL`；`require_tenant_roles(*roles)` 断言 `provider_id IS NULL`。
- 存储抽象 `from app.core.storage import storage`：`storage.put_object(key, bytes, content_type)`、`storage.get_url(key) -> str`（签名 URL）。测试环境用 `LocalFileStorage`，无需 mock。
- `should_reveal_owner_phone` / `display_owner_phone` 在 `app/core/phone_visibility.py`；`should_reveal_owner_phone` 对 `role="legal"` 只看 `legal_case_stage`，传 `None` → 返回 `False`（脱敏）。
- 当前 Alembic head：`24016v220b`（`alembic heads` 已确认）。
- `log_audit` 在 `app/services/audit.py`，签名 `log_audit(db, *, actor_user_id, actor_role, tenant_id, action, target_type, target_id, payload)`。

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `poc/backend/app/models/legal_conversion.py` | 新增 `LegalConversionRequestMaterial` ORM 模型 | 改 |
| `poc/backend/alembic/versions/24017_v220_legal_conv_req_material.py` | 建表迁移 | 建 |
| `poc/backend/app/schemas/provider_legal.py` | provider-legal 端点的 Pydantic schema | 建 |
| `poc/backend/app/schemas/legal_conversion_request.py` | 补材料 schema + 物业侧详情 schema | 改 |
| `poc/backend/app/api/provider_legal.py` | `/provider/legal/*` 7 个端点 + 作用域 helper | 建 |
| `poc/backend/app/api/legal_conversion_requests.py` | 补物业侧端点 8/9 | 改 |
| `poc/backend/app/main.py` | 注册 `provider_legal` router | 改 |
| `poc/backend/tests/test_legal_conv_req_material.py` | 模型 round-trip 测试 | 建 |
| `poc/backend/tests/api/test_provider_legal.py` | provider-legal 端点测试 | 建 |
| `poc/backend/tests/api/test_legal_conversion_requests.py` | 物业侧端点 8/9 测试 | 改 |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | §9.1 标注已实现 | 改 |

---

## Task 1: `LegalConversionRequestMaterial` 模型 + 迁移

**Files:**
- Modify: `poc/backend/app/models/legal_conversion.py`（文件末尾追加一个模型类）
- Create: `poc/backend/alembic/versions/24017_v220_legal_conv_req_material.py`
- Test: `poc/backend/tests/test_legal_conv_req_material.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `poc/backend/tests/test_legal_conv_req_material.py`：

```python
"""§9.1 — LegalConversionRequestMaterial 模型 round-trip 测试。"""
from __future__ import annotations


def test_legal_conversion_request_material_round_trip(
    db_session, seeded_tenant, seeded_case, seeded_member_user
):
    from app.models.legal_conversion import (
        LegalConversionRequest,
        LegalConversionRequestMaterial,
    )

    req = LegalConversionRequest(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        requester_user_id=seeded_member_user.id,
        requester_role="legal",
        status="pending",
    )
    db_session.add(req)
    db_session.flush()

    mat = LegalConversionRequestMaterial(
        request_id=req.id,
        tenant_id=seeded_tenant.id,
        object_key="legal_conv_req_materials/1/1/abc.pdf",
        filename="证据材料.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        uploaded_by=seeded_member_user.id,
    )
    db_session.add(mat)
    db_session.flush()
    db_session.refresh(mat)

    got = db_session.get(LegalConversionRequestMaterial, mat.id)
    assert got is not None
    assert got.request_id == req.id
    assert got.tenant_id == seeded_tenant.id
    assert got.filename == "证据材料.pdf"
    assert got.content_type == "application/pdf"
    assert got.size_bytes == 2048
    assert got.uploaded_by == seeded_member_user.id
    assert got.created_at is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/test_legal_conv_req_material.py -v`
Expected: FAIL — `ImportError: cannot import name 'LegalConversionRequestMaterial'`.

- [ ] **Step 3: 追加 ORM 模型**

在 `poc/backend/app/models/legal_conversion.py` **文件末尾**追加：

```python
class LegalConversionRequestMaterial(Base, TimestampMixin):
    """§9.1 — 服务商法务为某「法务转化请求」上传的补充材料附件。

    归属经 request → case → project.provider_id 推导，故不设 provider_id 列。
    """

    __tablename__ = "legal_conversion_request_material"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_conversion_request.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(sa.Text)
    size_bytes: Mapped[int | None] = mapped_column(sa.Integer)
    uploaded_by: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("ix_legal_conv_req_material_request", "request_id"),
        sa.Index("ix_legal_conv_req_material_tenant", "tenant_id"),
    )
```

> `Base`、`TimestampMixin`、`sa`、`Mapped`、`mapped_column` 在该文件顶部已 import（`LegalConversionRequest` 用的就是它们）—— 无需新增 import。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/test_legal_conv_req_material.py -v`
Expected: PASS — 1 passed。

- [ ] **Step 5: 建迁移**

新建 `poc/backend/alembic/versions/24017_v220_legal_conv_req_material.py`：

```python
"""§9.1 — 法务转化请求补充材料附件表

Revision ID: 24017v220c
Revises: 24016v220b
Create Date: 2026-05-16 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24017v220c"
down_revision: str | None = "24016v220b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legal_conversion_request_material",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["request_id"], ["legal_conversion_request.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["user_account.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_legal_conv_req_material_request",
        "legal_conversion_request_material",
        ["request_id"],
    )
    op.create_index(
        "ix_legal_conv_req_material_tenant",
        "legal_conversion_request_material",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legal_conv_req_material_tenant",
        table_name="legal_conversion_request_material",
    )
    op.drop_index(
        "ix_legal_conv_req_material_request",
        table_name="legal_conversion_request_material",
    )
    op.drop_table("legal_conversion_request_material")
```

- [ ] **Step 6: 确认迁移链完整**

Run: `cd poc/backend && python3.12 -m alembic heads`
Expected: 输出 `24017v220c (head)` —— 新迁移是唯一 head。

- [ ] **Step 7: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/models/legal_conversion.py poc/backend/alembic/versions/24017_v220_legal_conv_req_material.py poc/backend/tests/test_legal_conv_req_material.py
git commit -m "feat(v2.2): §9.1 legal_conversion_request_material 模型 + 迁移"
```

---

## Task 2: provider-legal 路由骨架 + 案件浏览（端点 1、2）

**Files:**
- Create: `poc/backend/app/schemas/provider_legal.py`
- Create: `poc/backend/app/api/provider_legal.py`
- Modify: `poc/backend/app/main.py`（加 import + `include_router`）
- Test: `poc/backend/tests/api/test_provider_legal.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `poc/backend/tests/api/test_provider_legal.py`：

```python
"""§9.1 — 服务商法务端点测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient


def _seed_provider_env(db_session, tenant, *, provider_name, owner_phone, project_status="active"):
    """建 provider + project(provider_id) + owner + case + provider-legal 用户 + token。

    返回 SimpleNamespace(provider, project, owner, case, user, token)。
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.case import CollectionCase, OwnerProfile, Project
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name=provider_name,
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900000000"),
    )
    db_session.add(provider)
    db_session.flush()

    project = Project(
        tenant_id=tenant.id,
        name=f"{provider_name}-项目",
        provider_id=provider.id,
        status=project_status,
        plan_end=datetime.now(UTC) + timedelta(days=90),
    )
    db_session.add(project)
    db_session.flush()

    owner = OwnerProfile(
        tenant_id=tenant.id,
        name="业主测试",
        phone_enc=encrypt_phone(owner_phone),
        building="2栋",
        room="202",
    )
    db_session.add(owner)
    db_session.flush()

    case = CollectionCase(
        tenant_id=tenant.id,
        project_id=project.id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("5000.00"),
        months_overdue=4,
        priority_score=900,
    )
    db_session.add(case)
    db_session.flush()

    user = UserAccount(
        name=f"{provider_name}-法务",
        phone_enc=encrypt_phone(owner_phone),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role="legal",
        provider_id=provider.id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()

    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "legal",
        "provider_id": provider.id,
        "scope": f"tenant:{tenant.id}",
    })
    return SimpleNamespace(
        provider=provider, project=project, owner=owner, case=case, user=user, token=token
    )


@pytest.fixture
def api(db_session):
    from app.core.db import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as cli:
        yield cli
    app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_list_cases_rejects_property_side_legal(api, db_session, seeded_tenant):
    """物业侧 legal（provider_id 空）访问 /provider/legal/* → 403。"""
    from app.core.security import create_access_token
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    u = UserAccount(name="物业法务", phone_enc=encrypt_phone("13700000001"),
                    password_hash=get_password_hash("pw"), is_active=True)
    db_session.add(u)
    db_session.flush()
    db_session.add(UserTenantMembership(
        tenant_id=seeded_tenant.id, user_id=u.id, role="legal", is_active=True))
    db_session.flush()
    token = create_access_token({
        "sub": str(u.id), "user_id": u.id, "tenant_id": seeded_tenant.id,
        "role": "legal", "scope": f"tenant:{seeded_tenant.id}",
    })
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(token))
    assert resp.status_code == 403


def test_list_cases_returns_own_provider_cases(api, db_session, seeded_tenant):
    """服务商法务只看到本服务商项目下的案件。"""
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["case_id"] == env.case.id
    assert item["project_id"] == env.project.id
    # 电话脱敏
    assert item["owner_phone_masked"] == "137****5678"


def test_list_cases_cross_provider_isolation(api, db_session, seeded_tenant):
    """服务商A 的法务看不到服务商B 的案件。"""
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    _seed_provider_env(db_session, seeded_tenant,
                       provider_name="服务商B", owner_phone="13755556666")
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(env_a.token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["case_id"] == env_a.case.id


def test_get_case_detail(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.get(f"/api/v1/provider/legal/cases/{env.case.id}", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_id"] == env.case.id
    assert body["owner_phone_masked"] == "137****5678"
    assert body["stage"] == "new"
    assert body["call_count"] == 0


def test_get_case_detail_cross_provider_404(api, db_session, seeded_tenant):
    """服务商A 的法务取服务商B 的案件 → 404。"""
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    resp = api.get(f"/api/v1/provider/legal/cases/{env_b.case.id}", headers=_auth(env_a.token))
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -v`
Expected: FAIL — `/api/v1/provider/legal/cases` 返回 404（路由未注册）。

- [ ] **Step 3: 建 schema 文件**

新建 `poc/backend/app/schemas/provider_legal.py`：

```python
"""§9.1 — 服务商法务端点 Pydantic schema。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProviderLegalCaseListItem(BaseModel):
    """服务商法务案件列表项。"""

    case_id: int
    owner_name: str | None = None
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    stage: str


class ProviderLegalCaseDetail(BaseModel):
    """服务商法务案件详情（整理材料用）。"""

    case_id: int
    owner_name: str | None = None
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    pool_type: str
    stage: str
    status: str
    amount_owed: Decimal | None = None
    principal_amount: Decimal | None = None
    late_fee_amount: Decimal | None = None
    months_overdue: int | None = None
    arrears_reason: str | None = None
    last_contact_at: datetime | None = None
    monthly_contact_count: int
    priority_score: int
    call_count: int = 0
    last_call_at: datetime | None = None


class ProviderLegalConversionRequestCreate(BaseModel):
    """服务商法务发起法务转化请求入参。"""

    reason: str | None = Field(None, max_length=2000)
```

- [ ] **Step 4: 建路由文件**

新建 `poc/backend/app/api/provider_legal.py`：

```python
"""§9.1 — 服务商法务职责边界。

服务商侧法务（role='legal' + provider_id 非空）专用端点。整路由用
require_provider_roles("legal") 守卫；案件归属经 CollectionCase.project_id →
Project.provider_id 推导。物业侧 legal 端点不受影响。
"""
from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import display_owner_phone, should_reveal_owner_phone
from app.core.roles import ROLE_LEGAL
from app.core.security import get_token_payload, require_provider_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider_legal import (
    ProviderLegalCaseDetail,
    ProviderLegalCaseListItem,
)

router = APIRouter()


def _ctx(payload: dict) -> tuple[int, int, int]:
    """返回 (tenant_id, provider_id, user_id)。require_provider_roles 已保证 provider_id 非空。"""
    tenant_id = int(payload.get("tenant_id") or 0)
    provider_id = payload.get("provider_id")
    user_id = int(payload.get("user_id") or 0)
    if not tenant_id or provider_id is None or not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "缺少必要的租户/服务商上下文"},
        )
    return tenant_id, int(provider_id), user_id


def _provider_legal_case_filter(tenant_id: int, provider_id: int):
    """案件可见性子句：本服务商 tenant 内 active 且服务期内项目下的案件。"""
    return sa.and_(
        CollectionCase.tenant_id == tenant_id,
        CollectionCase.project_id.in_(
            select(Project.id).where(
                Project.tenant_id == tenant_id,
                Project.provider_id == provider_id,
                Project.status == "active",
                sa.or_(Project.plan_end.is_(None), Project.plan_end >= func.now()),
            )
        ),
    )


def _owner_phone_reveal(provider_id: int) -> bool:
    """服务商法务整理转化前的普通案件 —— 无 LegalCase.stage → 脱敏。"""
    return should_reveal_owner_phone(
        role=ROLE_LEGAL, provider_id=provider_id, legal_case_stage=None
    )


@router.get("/cases", response_model=PaginatedResponse[ProviderLegalCaseListItem])
def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderLegalCaseListItem]:
    tenant_id, provider_id, _ = _ctx(payload)
    case_filter = _provider_legal_case_filter(tenant_id, provider_id)
    total = int(db.execute(select(func.count(CollectionCase.id)).where(case_filter)).scalar_one())
    rows = db.execute(
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(case_filter)
        .order_by(desc(CollectionCase.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    reveal = _owner_phone_reveal(provider_id)
    items = [
        ProviderLegalCaseListItem(
            case_id=c.id,
            owner_name=o.name,
            owner_phone_masked=display_owner_phone(o.phone_enc, reveal=reveal),
            building=o.building,
            room=o.room,
            project_id=c.project_id,
            project_name=pn,
            amount_owed=c.amount_owed,
            months_overdue=c.months_overdue,
            stage=c.stage,
        )
        for c, o, pn in rows
    ]
    return PaginatedResponse[ProviderLegalCaseListItem](
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/cases/{case_id}", response_model=ProviderLegalCaseDetail)
def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalCaseDetail:
    tenant_id, provider_id, _ = _ctx(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(
            CollectionCase.id == case_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner, project_name = row
    call_count = int(
        db.execute(
            select(func.count(CallRecord.id)).where(CallRecord.case_id == case_id)
        ).scalar_one()
    )
    last_call_at = db.execute(
        select(func.max(CallRecord.started_at)).where(CallRecord.case_id == case_id)
    ).scalar_one_or_none()
    reveal = _owner_phone_reveal(provider_id)
    return ProviderLegalCaseDetail(
        case_id=case.id,
        owner_name=owner.name,
        owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal),
        building=owner.building,
        room=owner.room,
        project_id=case.project_id,
        project_name=project_name,
        pool_type=case.pool_type,
        stage=case.stage,
        status=case.status,
        amount_owed=case.amount_owed,
        principal_amount=case.principal_amount,
        late_fee_amount=case.late_fee_amount,
        months_overdue=case.months_overdue,
        arrears_reason=case.arrears_reason,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        priority_score=case.priority_score,
        call_count=call_count,
        last_call_at=last_call_at,
    )
```

- [ ] **Step 5: 注册路由**

在 `poc/backend/app/main.py`：

(a) 在文件顶部 `app.api` import 区追加一行（与现有 `from app.api import (notifications as notifications_api,)` 等并列）：

```python
from app.api import provider_legal
```

(b) 在 `app.include_router(legal_documents.router, ...)` 那一行**之后**追加：

```python
app.include_router(
    provider_legal.router, prefix="/api/v1/provider/legal", tags=["provider-legal"]
)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -v`
Expected: PASS — 5 passed。

- [ ] **Step 7: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/provider_legal.py poc/backend/app/api/provider_legal.py poc/backend/app/main.py poc/backend/tests/api/test_provider_legal.py
git commit -m "feat(v2.2): §9.1 provider-legal 路由 + 案件只读浏览端点"
```

---

## Task 3: 发起法务转化请求（端点 3）

**Files:**
- Modify: `poc/backend/app/schemas/provider_legal.py`（追加 `ProviderLegalRequestOut`）
- Modify: `poc/backend/app/api/provider_legal.py`（追加 helper + 端点）
- Test: `poc/backend/tests/api/test_provider_legal.py`（追加测试）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_provider_legal.py` **末尾**追加：

```python
def test_create_conversion_request(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "业主长期拒缴，建议走法务"},
        headers=_auth(env.token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == env.case.id
    assert body["status"] == "pending"
    assert body["reason"] == "业主长期拒缴，建议走法务"
    assert body["order_status"] is None

    from app.models.legal_conversion import LegalConversionRequest
    req = db_session.get(LegalConversionRequest, body["id"])
    assert req is not None
    assert req.requester_role == "legal"
    assert req.requester_user_id == env.user.id


def test_create_conversion_request_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env_b.case.id}/conversion-request",
        json={"reason": "x"},
        headers=_auth(env_a.token),
    )
    assert resp.status_code == 404


def test_create_conversion_request_duplicate_pending_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    first = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "第一次"}, headers=_auth(env.token),
    )
    assert first.status_code == 201
    second = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "第二次"}, headers=_auth(env.token),
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "ERR_REQUEST_PENDING"


def test_create_conversion_request_active_order_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    from app.models.legal_conversion import LegalConversionOrder
    order = LegalConversionOrder(
        tenant_id=seeded_tenant.id, case_id=env.case.id, status="in_service"
    )
    db_session.add(order)
    db_session.flush()
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "x"}, headers=_auth(env.token),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ERR_LEGAL_ORDER_EXISTS"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -k conversion_request -v`
Expected: FAIL — `POST .../conversion-request` 返回 404/405（端点不存在）。

- [ ] **Step 3: 追加 `ProviderLegalRequestOut` schema**

在 `poc/backend/app/schemas/provider_legal.py` **末尾**追加：

```python
class ProviderLegalRequestOut(BaseModel):
    """服务商法务的法务转化请求 —— 列表项 / 创建结果。"""

    id: int
    tenant_id: int
    case_id: int
    owner_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    amount_owed: Decimal | None = None
    reason: str | None = None
    status: str
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None
    related_order_id: int | None = None
    order_status: str | None = None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: 追加 helper + 端点**

在 `poc/backend/app/api/provider_legal.py`：

(a) 顶部 import 区，把 `legal_conversion` 模型与 `log_audit`、新 schema 加进来。将现有

```python
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider_legal import (
    ProviderLegalCaseDetail,
    ProviderLegalCaseListItem,
)
```

替换为：

```python
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import (
    LegalConversionOrder,
    LegalConversionRequest,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider_legal import (
    ProviderLegalCaseDetail,
    ProviderLegalCaseListItem,
    ProviderLegalConversionRequestCreate,
    ProviderLegalRequestOut,
)
from app.services.audit import log_audit
```

(b) 文件末尾追加 helper `_request_to_out` 与端点：

```python
def _request_to_out(db: Session, req: LegalConversionRequest) -> ProviderLegalRequestOut:
    """把 LegalConversionRequest 组装成 ProviderLegalRequestOut（含订单高阶状态）。"""
    case = db.get(CollectionCase, req.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case else None
    project = db.get(Project, case.project_id) if case and case.project_id else None
    order_status: str | None = None
    if req.related_order_id is not None:
        order = db.get(LegalConversionOrder, req.related_order_id)
        order_status = order.status if order else None
    return ProviderLegalRequestOut(
        id=req.id,
        tenant_id=req.tenant_id,
        case_id=req.case_id,
        owner_name=owner.name if owner else None,
        project_id=case.project_id if case else None,
        project_name=project.name if project else None,
        amount_owed=case.amount_owed if case else None,
        reason=req.reason,
        status=req.status,
        reviewer_note=req.reviewer_note,
        reviewed_at=req.reviewed_at,
        related_order_id=req.related_order_id,
        order_status=order_status,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.post(
    "/cases/{case_id}/conversion-request",
    response_model=ProviderLegalRequestOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_conversion_request(
    case_id: int,
    body: ProviderLegalConversionRequestCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalRequestOut:
    tenant_id, provider_id, user_id = _ctx(payload)
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == case_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    active_order = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.case_id == case_id,
            LegalConversionOrder.status.in_(("pending", "dispatched", "in_service")),
        )
    ).scalar_one_or_none()
    if active_order is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_LEGAL_ORDER_EXISTS",
                "message": "该案件已存在进行中的法务转化订单",
            },
        )
    pending_req = db.execute(
        select(LegalConversionRequest).where(
            LegalConversionRequest.case_id == case_id,
            LegalConversionRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if pending_req is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_REQUEST_PENDING",
                "message": "该案件已有待审批的转法务申请",
            },
        )
    req = LegalConversionRequest(
        tenant_id=tenant_id,
        case_id=case_id,
        requester_user_id=user_id,
        requester_role=ROLE_LEGAL,
        reason=body.reason,
        status="pending",
    )
    db.add(req)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=ROLE_LEGAL,
        tenant_id=tenant_id,
        action="legal_conversion_request.created",
        target_type="legal_conversion_request",
        target_id=req.id,
        payload={"case_id": case_id, "reason": body.reason}
        if body.reason
        else {"case_id": case_id},
    )
    db.commit()
    db.refresh(req)
    return _request_to_out(db, req)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -v`
Expected: PASS — 9 passed（Task 2 的 5 条 + 本任务 4 条）。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/provider_legal.py poc/backend/app/api/provider_legal.py poc/backend/tests/api/test_provider_legal.py
git commit -m "feat(v2.2): §9.1 服务商法务发起法务转化请求端点"
```

---

## Task 4: 补充材料上传 / 下载（端点 4、5）

**Files:**
- Modify: `poc/backend/app/schemas/legal_conversion_request.py`（追加材料 schema）
- Modify: `poc/backend/app/api/provider_legal.py`（追加 helper + 2 端点）
- Test: `poc/backend/tests/api/test_provider_legal.py`（追加测试）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_provider_legal.py` **末尾**追加：

```python
def _create_request(db_session, env):
    """直接建一个 pending 的 LegalConversionRequest，返回它。"""
    from app.models.legal_conversion import LegalConversionRequest
    req = LegalConversionRequest(
        tenant_id=env.case.tenant_id, case_id=env.case.id,
        requester_user_id=env.user.id, requester_role="legal", status="pending",
    )
    db_session.add(req)
    db_session.flush()
    return req


def test_upload_and_download_material(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    up = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=_auth(env.token),
    )
    assert up.status_code == 201, up.text
    mat = up.json()
    assert mat["request_id"] == req.id
    assert mat["filename"] == "证据.pdf"
    assert mat["size_bytes"] == len(b"%PDF-1.4 fake")

    dl = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials/{mat['id']}",
        headers=_auth(env.token),
    )
    assert dl.status_code == 200, dl.text
    assert dl.json()["download_url"]
    assert dl.json()["filename"] == "证据.pdf"


def test_upload_material_empty_file_422(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=_auth(env.token),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "ERR_EMPTY_FILE"


def test_upload_material_non_pending_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    req.status = "approved"
    db_session.flush()
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4", "application/pdf")},
        headers=_auth(env.token),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ERR_REQUEST_NOT_PENDING"


def test_upload_material_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    req_b = _create_request(db_session, env_b)
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4", "application/pdf")},
        headers=_auth(env_a.token),
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -k material -v`
Expected: FAIL — materials 端点不存在（404/405）。

- [ ] **Step 3: 追加材料 schema**

在 `poc/backend/app/schemas/legal_conversion_request.py` **末尾**追加：

```python
class LegalConversionRequestMaterialOut(BaseModel):
    """法务转化请求的补充材料元数据。"""

    id: int
    request_id: int
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LegalConversionRequestMaterialDownloadOut(BaseModel):
    """补充材料下载链接。"""

    download_url: str
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    expires_in_sec: int = 3600
```

> `BaseModel`、`datetime` 在该文件顶部已 import。

- [ ] **Step 4: 追加 helper + 2 端点**

在 `poc/backend/app/api/provider_legal.py`：

(a) 顶部 import 区：把 `uuid` 与 `File`/`UploadFile`、storage、新模型、新 schema 加进来。将

```python
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
```

替换为：

```python
import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
```

并在 import 区追加：

```python
from app.core.storage import storage
from app.models.legal_conversion import LegalConversionRequestMaterial
from app.schemas.legal_conversion_request import (
    LegalConversionRequestMaterialDownloadOut,
    LegalConversionRequestMaterialOut,
)
```

(b) 在 `router = APIRouter()` 之后追加模块常量：

```python
MAX_MATERIAL_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "image/",
    "text/",
)
```

(c) 文件末尾追加 helper `_load_provider_request` 与 2 个端点：

```python
def _load_provider_request(
    db: Session, request_id: int, tenant_id: int, provider_id: int
) -> LegalConversionRequest:
    """加载请求并校验其案件在本服务商作用域内；不在则 404。"""
    req = db.execute(
        select(LegalConversionRequest)
        .join(CollectionCase, CollectionCase.id == LegalConversionRequest.case_id)
        .where(
            LegalConversionRequest.id == request_id,
            LegalConversionRequest.tenant_id == tenant_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "请求不存在"},
        )
    return req


@router.post(
    "/conversion-requests/{request_id}/materials",
    response_model=LegalConversionRequestMaterialOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_material(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> LegalConversionRequestMaterialOut:
    tenant_id, provider_id, user_id = _ctx(payload)
    req = _load_provider_request(db, request_id, tenant_id, provider_id)
    if req.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_REQUEST_NOT_PENDING",
                "message": "请求已审批，材料已锁定",
            },
        )
    mime = file.content_type or ""
    if mime and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_MIME", "message": f"不支持的文件类型: {mime}"},
        )
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_EMPTY_FILE", "message": "上传文件为空"},
        )
    if len(raw) > MAX_MATERIAL_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "ERR_FILE_TOO_LARGE", "message": "文件超过 50MB 限制"},
        )
    filename = file.filename or f"material_{uuid.uuid4().hex[:8]}"
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    object_key = f"legal_conv_req_materials/{tenant_id}/{request_id}/{uuid.uuid4().hex}.{ext}"
    try:
        storage.put_object(object_key, raw, mime or "application/octet-stream")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "文件存储失败"},
        ) from exc
    material = LegalConversionRequestMaterial(
        request_id=request_id,
        tenant_id=tenant_id,
        object_key=object_key,
        filename=filename,
        content_type=mime or None,
        size_bytes=len(raw),
        uploaded_by=user_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return LegalConversionRequestMaterialOut.model_validate(material)


@router.get(
    "/conversion-requests/{request_id}/materials/{material_id}",
    response_model=LegalConversionRequestMaterialDownloadOut,
)
def download_material(
    request_id: int,
    material_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestMaterialDownloadOut:
    tenant_id, provider_id, _ = _ctx(payload)
    _load_provider_request(db, request_id, tenant_id, provider_id)
    material = db.get(LegalConversionRequestMaterial, material_id)
    if material is None or material.request_id != request_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "材料不存在"},
        )
    try:
        url = storage.get_url(material.object_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "无法生成下载链接"},
        ) from exc
    return LegalConversionRequestMaterialDownloadOut(
        download_url=url,
        filename=material.filename,
        content_type=material.content_type,
        size_bytes=material.size_bytes,
    )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -v`
Expected: PASS — 13 passed（前 9 条 + 本任务 4 条）。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/legal_conversion_request.py poc/backend/app/api/provider_legal.py poc/backend/tests/api/test_provider_legal.py
git commit -m "feat(v2.2): §9.1 服务商法务补充材料上传/下载端点"
```

---

## Task 5: 跟进进度 — 请求列表 + 详情（端点 6、7）

**Files:**
- Modify: `poc/backend/app/schemas/provider_legal.py`（追加 `ProviderLegalRequestDetail`）
- Modify: `poc/backend/app/api/provider_legal.py`（追加 2 端点）
- Test: `poc/backend/tests/api/test_provider_legal.py`（追加测试）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_provider_legal.py` **末尾**追加：

```python
def test_list_conversion_requests(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    resp = api.get("/api/v1/provider/legal/conversion-requests", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == req.id
    assert body["items"][0]["status"] == "pending"


def test_list_conversion_requests_cross_provider_isolation(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    _create_request(db_session, env_a)
    _create_request(db_session, env_b)
    resp = api.get("/api/v1/provider/legal/conversion-requests", headers=_auth(env_a.token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_conversion_request_detail_with_materials_and_order_status(
    api, db_session, seeded_tenant
):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    # 关联一个订单，验证 order_status 透出
    from app.models.legal_conversion import LegalConversionOrder
    order = LegalConversionOrder(
        tenant_id=seeded_tenant.id, case_id=env.case.id, status="internal_processing"
    )
    db_session.add(order)
    db_session.flush()
    req.related_order_id = order.id
    db_session.flush()
    # 上传一个材料
    up = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4 x", "application/pdf")},
        headers=_auth(env.token),
    )
    assert up.status_code == 201

    resp = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req.id}", headers=_auth(env.token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == req.id
    assert body["order_status"] == "internal_processing"
    assert len(body["materials"]) == 1
    assert body["materials"][0]["filename"] == "证据.pdf"


def test_get_conversion_request_detail_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    req_b = _create_request(db_session, env_b)
    resp = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}", headers=_auth(env_a.token)
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -k conversion_request -v`
Expected: FAIL — `GET /conversion-requests` 与 `GET /conversion-requests/{id}` 不存在。

- [ ] **Step 3: 追加 `ProviderLegalRequestDetail` schema**

在 `poc/backend/app/schemas/provider_legal.py` **末尾**追加：

```python
class ProviderLegalRequestDetail(ProviderLegalRequestOut):
    """请求详情 —— 在列表项基础上带补充材料列表。"""

    materials: list[LegalConversionRequestMaterialOut] = []
```

并在该文件顶部 import 区追加：

```python
from app.schemas.legal_conversion_request import LegalConversionRequestMaterialOut
```

- [ ] **Step 4: 追加 2 端点**

在 `poc/backend/app/api/provider_legal.py`：

(a) import 区把 `ProviderLegalRequestDetail` 加进 `app.schemas.provider_legal` 的 import 列表（与 `ProviderLegalRequestOut` 并列）。

(b) 文件末尾追加 2 个端点：

```python
@router.get(
    "/conversion-requests",
    response_model=PaginatedResponse[ProviderLegalRequestOut],
)
def list_conversion_requests(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderLegalRequestOut]:
    tenant_id, provider_id, _ = _ctx(payload)
    req_filter = sa.and_(
        LegalConversionRequest.tenant_id == tenant_id,
        LegalConversionRequest.case_id.in_(
            select(CollectionCase.id).where(
                _provider_legal_case_filter(tenant_id, provider_id)
            )
        ),
    )
    total = int(
        db.execute(
            select(func.count(LegalConversionRequest.id)).where(req_filter)
        ).scalar_one()
    )
    reqs = (
        db.execute(
            select(LegalConversionRequest)
            .where(req_filter)
            .order_by(desc(LegalConversionRequest.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = [_request_to_out(db, r) for r in reqs]
    return PaginatedResponse[ProviderLegalRequestOut](
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/conversion-requests/{request_id}",
    response_model=ProviderLegalRequestDetail,
)
def get_conversion_request(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalRequestDetail:
    tenant_id, provider_id, _ = _ctx(payload)
    req = _load_provider_request(db, request_id, tenant_id, provider_id)
    materials = (
        db.execute(
            select(LegalConversionRequestMaterial)
            .where(LegalConversionRequestMaterial.request_id == request_id)
            .order_by(LegalConversionRequestMaterial.id)
        )
        .scalars()
        .all()
    )
    base = _request_to_out(db, req)
    return ProviderLegalRequestDetail(
        **base.model_dump(),
        materials=[
            LegalConversionRequestMaterialOut.model_validate(m) for m in materials
        ],
    )
```

> 注：`get_conversion_request` 路由路径 `/conversion-requests/{request_id}` 与 Task 4 的 `/conversion-requests/{request_id}/materials/{material_id}` 不冲突 —— FastAPI 按路径段数精确匹配。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_provider_legal.py -v`
Expected: PASS — 17 passed（前 13 条 + 本任务 4 条）。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/provider_legal.py poc/backend/app/api/provider_legal.py poc/backend/tests/api/test_provider_legal.py
git commit -m "feat(v2.2): §9.1 服务商法务请求列表 + 详情端点"
```

---

## Task 6: 物业侧请求详情 + 材料下载（端点 8、9）

**Files:**
- Modify: `poc/backend/app/schemas/legal_conversion_request.py`（追加 `LegalConversionRequestDetailOut`）
- Modify: `poc/backend/app/api/legal_conversion_requests.py`（追加 2 端点）
- Test: `poc/backend/tests/api/test_legal_conversion_requests.py`（追加测试）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_legal_conversion_requests.py` **末尾**追加：

```python
def _seed_request_with_material(db_session, seeded_tenant, seeded_case, uploader_id):
    """建一个 pending 请求 + 一条补充材料，返回 (request, material)。"""
    from app.models.legal_conversion import (
        LegalConversionRequest,
        LegalConversionRequestMaterial,
    )
    req = LegalConversionRequest(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        requester_user_id=uploader_id, requester_role="legal", status="pending",
    )
    db_session.add(req)
    db_session.flush()
    mat = LegalConversionRequestMaterial(
        request_id=req.id, tenant_id=seeded_tenant.id,
        object_key=f"legal_conv_req_materials/{seeded_tenant.id}/{req.id}/x.pdf",
        filename="服务商材料.pdf", content_type="application/pdf",
        size_bytes=128, uploaded_by=uploader_id,
    )
    db_session.add(mat)
    db_session.flush()
    return req, mat


def test_property_reviewer_sees_request_detail_with_materials(
    db_session, seeded_tenant, seeded_case, seeded_supervisor_user, supervisor_auth_headers
):
    from starlette.testclient import TestClient
    from app.main import app
    from app.core.db import get_db

    req, mat = _seed_request_with_material(
        db_session, seeded_tenant, seeded_case, seeded_supervisor_user.id
    )

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as cli:
            detail = cli.get(
                f"/api/v1/legal-conversion-requests/{req.id}",
                headers=supervisor_auth_headers,
            )
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["id"] == req.id
            assert len(body["materials"]) == 1
            assert body["materials"][0]["filename"] == "服务商材料.pdf"

            dl = cli.get(
                f"/api/v1/legal-conversion-requests/{req.id}/materials/{mat.id}",
                headers=supervisor_auth_headers,
            )
            assert dl.status_code == 200, dl.text
            assert dl.json()["download_url"]
    finally:
        app.dependency_overrides.clear()


def test_property_request_detail_cross_tenant_404(
    db_session, seeded_tenant, seeded_case, seeded_supervisor_user, supervisor_auth_headers
):
    from starlette.testclient import TestClient
    from app.main import app
    from app.core.db import get_db
    from app.core.crypto import encrypt_phone
    from app.models.legal_conversion import LegalConversionRequest
    from app.models.tenant import Tenant

    other = Tenant(name="别家物业", admin_phone_enc=encrypt_phone("13800000000"),
                    plan="trial", is_active=True)
    db_session.add(other)
    db_session.flush()
    foreign_req = LegalConversionRequest(
        tenant_id=other.id, case_id=seeded_case.id,
        requester_user_id=seeded_supervisor_user.id, requester_role="legal", status="pending",
    )
    db_session.add(foreign_req)
    db_session.flush()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as cli:
            resp = cli.get(
                f"/api/v1/legal-conversion-requests/{foreign_req.id}",
                headers=supervisor_auth_headers,
            )
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_legal_conversion_requests.py -k "detail or cross_tenant" -v`
Expected: FAIL — `GET /legal-conversion-requests/{id}` 不存在（404/405）。

- [ ] **Step 3: 追加 `LegalConversionRequestDetailOut` schema**

在 `poc/backend/app/schemas/legal_conversion_request.py` **末尾**追加：

```python
class LegalConversionRequestDetailOut(LegalConversionRequestOut):
    """物业审批人看到的请求详情 —— 在 inbox 列表项基础上带补充材料 + 订单高阶状态。"""

    order_status: str | None = None
    materials: list[LegalConversionRequestMaterialOut] = []
```

- [ ] **Step 4: 追加 2 端点**

在 `poc/backend/app/api/legal_conversion_requests.py`：

(a) import 区：把 `LegalConversionOrder` 与 `LegalConversionRequestMaterial` 加进 `app.models.legal_conversion` import；把新 schema 加进 `app.schemas.legal_conversion_request` import；加 storage import。将

```python
from app.models.legal_conversion import LegalConversionRequest
```

替换为：

```python
from app.core.storage import storage
from app.models.legal_conversion import (
    LegalConversionOrder,
    LegalConversionRequest,
    LegalConversionRequestMaterial,
)
```

并把现有的

```python
from app.schemas.legal_conversion_request import (
    ApproveLegalConversionRequestBody,
    LegalConversionRequestOut,
    RejectLegalConversionRequestBody,
)
```

替换为：

```python
from app.schemas.legal_conversion_request import (
    ApproveLegalConversionRequestBody,
    LegalConversionRequestDetailOut,
    LegalConversionRequestMaterialDownloadOut,
    LegalConversionRequestMaterialOut,
    LegalConversionRequestOut,
    RejectLegalConversionRequestBody,
)
```

(b) 文件末尾追加 2 个端点：

```python
@router.get(
    "/legal-conversion-requests/{request_id}",
    response_model=LegalConversionRequestDetailOut,
)
def get_request_detail(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestDetailOut:
    """§9.1 — 物业审批人看请求详情 + 服务商法务上传的补充材料。"""
    tenant_id = _require_tenant(payload)
    request_row = db.get(LegalConversionRequest, request_id)
    if request_row is None or request_row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "申请不存在"},
        )
    (
        request_row,
        case,
        owner,
        project_name,
        requester_name,
        reviewer_name,
    ) = _load_request_with_context(db, request_id, tenant_id)
    contract_active = is_provider_contract_active(
        db, tenant_id, payload.get("provider_id")
    )
    owner_phone_reveal = should_reveal_owner_phone(
        role=payload.get("role", ""),
        provider_id=payload.get("provider_id"),
        contract_active=contract_active,
    )
    base = _row_to_out(
        request_row=request_row,
        case=case,
        owner=owner,
        project_name=project_name,
        requester_name=requester_name,
        reviewer_name=reviewer_name,
        owner_phone_reveal=owner_phone_reveal,
    )
    order_status: str | None = None
    if request_row.related_order_id is not None:
        order = db.get(LegalConversionOrder, request_row.related_order_id)
        order_status = order.status if order else None
    materials = (
        db.execute(
            select(LegalConversionRequestMaterial)
            .where(LegalConversionRequestMaterial.request_id == request_id)
            .order_by(LegalConversionRequestMaterial.id)
        )
        .scalars()
        .all()
    )
    return LegalConversionRequestDetailOut(
        **base.model_dump(),
        order_status=order_status,
        materials=[
            LegalConversionRequestMaterialOut.model_validate(m) for m in materials
        ],
    )


@router.get(
    "/legal-conversion-requests/{request_id}/materials/{material_id}",
    response_model=LegalConversionRequestMaterialDownloadOut,
)
def download_request_material(
    request_id: int,
    material_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestMaterialDownloadOut:
    """§9.1 — 物业审批人下载服务商法务上传的补充材料。"""
    tenant_id = _require_tenant(payload)
    material = db.get(LegalConversionRequestMaterial, material_id)
    if (
        material is None
        or material.request_id != request_id
        or material.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "材料不存在"},
        )
    try:
        url = storage.get_url(material.object_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "无法生成下载链接"},
        ) from exc
    return LegalConversionRequestMaterialDownloadOut(
        download_url=url,
        filename=material.filename,
        content_type=material.content_type,
        size_bytes=material.size_bytes,
    )
```

> `_load_request_with_context`、`_row_to_out`、`_require_tenant`、`REVIEWER_ROLES`、`is_provider_contract_active`、`should_reveal_owner_phone`、`get_token_payload`、`require_tenant_roles`、`HTTPException`、`http_status`、`select`、`Session`、`Annotated`、`UserAccount` 在该文件中均已存在/已 import（见文件现有 `approve`/`reject`/`list_requests` 端点）。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_legal_conversion_requests.py -v`
Expected: PASS — 既有用例 + 本任务 2 条全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/legal_conversion_request.py poc/backend/app/api/legal_conversion_requests.py poc/backend/tests/api/test_legal_conversion_requests.py
git commit -m "feat(v2.2): §9.1 物业侧请求详情 + 材料下载端点"
```

---

## Task 7: 标注设计文档 + 全量回归

**Files:**
- Modify: `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md:167-173`（§9.1 段落）

- [ ] **Step 1: 标注 §9.1 已实现**

打开 `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md`，在 `### 9.1 服务商法务` 小节的最后一条 bullet（`- 概念区分：...`）**之后**追加一行：

```
- ✅ **已实现(2026-05-16)**：新增 `/api/v1/provider/legal/*` 路由(`require_provider_roles("legal")`)，服务商法务可只读浏览本服务商项目下案件、上传补充材料、发起法务转化请求、跟进请求+订单高阶状态；审批/内部订单处理/律所派单仍物业专属。详见 `docs/superpowers/specs/2026-05-16-provider-legal-boundary-design.md`。
```

- [ ] **Step 2: 全量后端回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: PASS — 全量绿（基线 684 passed，§9.1 新增约 18 条 → 约 702 passed），无 FAILED / ERROR。

若有 FAIL：定位是否本次改动引入。`provider_legal` / `legal_conversion_requests` / `legal_conversion` 相关失败必须修复后再继续；与 §9.1 无关的预存失败如实记录。

- [ ] **Step 3: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-16-role-model-refactor-design.md
git commit -m "docs(v2.2): §9.1 标注已实现"
```

---

## Self-Review

**1. Spec coverage（对照设计文档 §2–§8）：**
- §2 架构（专用路由 + `require_provider_roles("legal")`）→ Task 2 Step 4 ✅
- §3 数据模型（`legal_conversion_request_material` 表 + 迁移）→ Task 1 ✅
- §4.1 端点 1–7 → Task 2（1,2）/ Task 3（3）/ Task 4（4,5）/ Task 5（6,7）✅
- §4.2 物业侧端点 8,9 → Task 6 ✅
- §5 数据隔离（`Project.provider_id` 过滤、请求经 case→project 归属）→ `_provider_legal_case_filter` + `_load_provider_request`（Task 2/4）；跨服务商隔离测试 Task 2/3/4/5 均覆盖 ✅
- §6 电话脱敏（`should_reveal_owner_phone(role="legal", legal_case_stage=None)` → 脱敏）→ `_owner_phone_reveal`（Task 2），测试断言 `137****5678` ✅
- §7 安全（结构性隔离 —— 审批等能力不在新路由里；`require_tenant_roles` 不动）→ 物业侧端点仍 `require_tenant_roles`，新路由不含审批端点 ✅
- §8 测试矩阵 → 守卫拒绝（Task 2）、跨服务商隔离（Task 2/3/4/5）、发起+防重（Task 3）、材料上传/下载/锁定（Task 4）、进度（Task 5）、物业侧（Task 6）、电话脱敏（Task 2）全覆盖 ✅
- §9 文件清单 → 全部有对应 Task ✅

**2. Placeholder scan:** 无 TBD/TODO/「类似 Task N」/「适当处理」。每个 code step 给出完整代码与精确命令。✅

**3. Type consistency:**
- `_provider_legal_case_filter(tenant_id, provider_id)` —— Task 2 定义，Task 3/4/5 调用，签名一致 ✅
- `_ctx(payload) -> (tenant_id, provider_id, user_id)` —— Task 2 定义，全任务复用 ✅
- `_request_to_out(db, req) -> ProviderLegalRequestOut` —— Task 3 定义，Task 5 复用 ✅
- `_load_provider_request(db, request_id, tenant_id, provider_id)` —— Task 4 定义，Task 5 复用 ✅
- `LegalConversionRequestMaterialOut` / `LegalConversionRequestMaterialDownloadOut` —— Task 4 在 `legal_conversion_request.py` schema 定义，Task 5（provider 详情）、Task 6（物业侧）复用 ✅
- `ProviderLegalRequestOut` → `ProviderLegalRequestDetail` 继承 —— Task 3 定义基类，Task 5 定义子类 ✅
- 端点路径 `/conversion-requests/{request_id}` 与 `/conversion-requests/{request_id}/materials/{material_id}` 段数不同，FastAPI 精确匹配，无冲突 ✅
- `LegalConversionRequestMaterial` 模型字段（`request_id`/`tenant_id`/`object_key`/`filename`/`content_type`/`size_bytes`/`uploaded_by`）—— Task 1 ORM 与迁移列一致 ✅
