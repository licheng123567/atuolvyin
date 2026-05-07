# Sprint 2: 案件管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 admin 批量导入案件、案件列表/详情/分配/阶段更新，supervisor 查看全部案件，agent 查看并认领公池案件，完成案件管理核心闭环。

**Architecture:** 后端新增三个 APIRouter（admin_cases / supervisor / agent_cases），全部通过 `require_roles` + JWT tenant_id 鉴权，共享 `_case_row_to_response` 辅助函数；ORM 模型 OwnerProfile / CollectionCase 已在 Alembic 初始迁移中建表，无需新迁移；前端增加 admin 案件列表页（含分配弹窗）、导入页、agent 案件页，Refine resources 注册 admin/cases / agent/cases。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 / pytest+httpx+testcontainers · TypeScript / React / Refine v5 / shadcn/ui / Tailwind CSS / lucide-react

---

## File Map

| 操作 | 路径 | 说明 |
|------|------|------|
| Modify | `poc/backend/app/schemas/case.py` | 加 OwnerInfo / CaseWithOwnerResponse / CaseImportRequest / CaseImportResponse / CaseStageUpdate / CaseAssignResponse |
| Modify | `poc/backend/tests/conftest.py` | 加 seeded_owner / seeded_case / seeded_supervisor_user / agent_auth_headers / supervisor_auth_headers |
| Create | `poc/backend/app/api/admin_cases.py` | import + list + detail + assign + stage 五个端点 |
| Create | `poc/backend/app/api/supervisor.py` | supervisor 查全部案件 |
| Create | `poc/backend/app/api/agent_cases.py` | agent 查自己/公池案件 + claim |
| Modify | `poc/backend/app/main.py` | 注册三个新 router |
| Create | `poc/backend/tests/api/test_admin_cases_import.py` | import 端点测试 |
| Create | `poc/backend/tests/api/test_admin_cases_list.py` | list + detail 端点测试 |
| Create | `poc/backend/tests/api/test_admin_cases_actions.py` | assign + stage 端点测试 |
| Create | `poc/backend/tests/api/test_supervisor_cases.py` | supervisor 端点测试 |
| Create | `poc/backend/tests/api/test_agent_cases.py` | agent 端点测试 |
| Modify | `frontend/src/config/nav.ts` | 给 admin / supervisor / agent 角色加案件入口 |
| Create | `frontend/src/pages/admin/cases/index.tsx` | 案件列表 + 分配弹窗 |
| Create | `frontend/src/pages/admin/cases/import.tsx` | 批量导入案件 |
| Create | `frontend/src/pages/agent/cases/index.tsx` | Agent 案件列表 + 认领 |
| Modify | `frontend/src/App.tsx` | 注册新 resources + 路由 |

---

## 关键约定（读代码前先看这里）

- **手机号存储**：Sprint 2 一律 `phone_enc = row.phone` (plaintext)，注释 `# plaintext until AES sprint`
- **优先级计算**：`int(float(amount_owed or 0) * 0.4 + float(months_overdue or 0) * 0.3)`
- **导入格式**：JSON body（`CaseImportRequest`），不用 multipart/form-data
- **Supervisor 范围**：当前租户全部案件（小组级作用域推迟到 Sprint 3）
- **已有 DB 表**：`collection_case` / `owner_profile` 已在初始 Alembic 迁移中建表，**本 Sprint 无需新迁移**
- **Refine v5 API**：
  - 导航：`useGo()` + `go({ to: "/path" })`
  - 数据：`query.data?.data`、`query.isLoading`
  - 自定义 POST：`useCreate({ resource: "admin/cases/assign", values: {...} })`
  - 分页：`currentPage`（不是 `current`）

---

## Task 1: 扩展 schemas/case.py

**Files:**
- Modify: `poc/backend/app/schemas/case.py`

- [ ] **Step 1: 在 case.py 顶部 import 块加 Literal**

打开 `poc/backend/app/schemas/case.py`，将第 3 行 `from typing import Optional` 改为：

```python
from typing import Literal, Optional
```

- [ ] **Step 2: 在文件末尾追加六个新 schema**

在 `poc/backend/app/schemas/case.py` 末尾追加：

```python
class OwnerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str
    building: Optional[str]
    room: Optional[str]
    do_not_call: bool


class CaseWithOwnerResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: Optional[int]
    owner: OwnerInfo
    assigned_to: Optional[int]
    pool_type: str
    stage: str
    amount_owed: Optional[Decimal]
    months_overdue: Optional[int]
    priority_score: int
    last_contact_at: Optional[datetime]
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class CaseImportRequest(BaseModel):
    rows: list[CaseImportRow] = Field(..., min_length=1, max_length=500)


class CaseImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class CaseStageUpdate(BaseModel):
    stage: Literal["new", "in_progress", "promised", "paid", "escalated", "closed"]


class CaseAssignResponse(BaseModel):
    updated_count: int
```

- [ ] **Step 3: 验证 schema 可导入（无 import 错误）**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -c "from app.schemas.case import CaseWithOwnerResponse, CaseImportRequest, CaseImportResponse, CaseStageUpdate, CaseAssignResponse; print('OK')"
```

期望输出：`OK`

- [ ] **Step 4: commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/schemas/case.py
git commit -m "feat(schemas): add Sprint 2 case schemas — OwnerInfo, CaseWithOwnerResponse, import/assign/stage types"
```

---

## Task 2: 添加 Sprint 2 测试 fixtures

**Files:**
- Modify: `poc/backend/tests/conftest.py`

- [ ] **Step 1: 在 conftest.py 末尾追加五个 fixture**

在 `poc/backend/tests/conftest.py` 末尾追加（在已有的 `admin_auth_headers` 之后）：

```python
from decimal import Decimal  # noqa: E402


@pytest.fixture
def seeded_owner(db_session, seeded_tenant):
    from app.models.case import OwnerProfile
    owner = OwnerProfile(
        tenant_id=seeded_tenant.id,
        name="张三",
        phone_enc="13712345678",  # plaintext until AES sprint
        building="1栋",
        room="101",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


@pytest.fixture
def seeded_case(db_session, seeded_tenant, seeded_owner):
    from app.models.case import CollectionCase
    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("3000.00"),
        months_overdue=3,
        priority_score=1200,  # int(3000*0.4 + 3*0.3)
    )
    db_session.add(case)
    db_session.flush()
    return case


@pytest.fixture
def seeded_supervisor_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    user = UserAccount(
        phone_enc="13922239222",
        name="督导李四",
        password_hash=get_password_hash("Supervisor@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="supervisor",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


@pytest.fixture
def agent_auth_headers(seeded_member_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supervisor_auth_headers(seeded_supervisor_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: 验证 conftest 可加载**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/conftest.py --collect-only 2>&1 | tail -5
```

期望：无 ImportError / SyntaxError

- [ ] **Step 3: commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): add Sprint 2 fixtures — seeded_owner, seeded_case, supervisor/agent auth headers"
```

---

## Task 3: POST /api/v1/admin/cases/import（TDD）

**Files:**
- Create: `poc/backend/app/api/admin_cases.py`
- Create: `poc/backend/tests/api/test_admin_cases_import.py`

- [ ] **Step 1: 写测试（先写，确保 FAIL）**

创建 `poc/backend/tests/api/test_admin_cases_import.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_cases_creates_owner_and_case(
    client: AsyncClient, admin_auth_headers, seeded_tenant
):
    payload = {
        "rows": [
            {
                "name": "李明",
                "phone": "13800001111",
                "building": "2栋",
                "room": "202",
                "amount_owed": "1500.00",
                "months_overdue": 2,
            }
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped"] == 0
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_import_duplicate_phone_reuses_owner(
    client: AsyncClient, admin_auth_headers, seeded_owner
):
    payload = {
        "rows": [
            {
                "name": seeded_owner.name,
                "phone": seeded_owner.phone_enc,
                "amount_owed": "2000.00",
                "months_overdue": 1,
            }
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 1  # new case created, owner reused


@pytest.mark.asyncio
async def test_import_multiple_rows(
    client: AsyncClient, admin_auth_headers
):
    payload = {
        "rows": [
            {"name": "王五", "phone": "13811110001", "amount_owed": "800.00", "months_overdue": 1},
            {"name": "赵六", "phone": "13811110002", "amount_owed": "1200.00", "months_overdue": 4},
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["imported"] == 2


@pytest.mark.asyncio
async def test_import_requires_admin_role(client: AsyncClient, ops_auth_headers):
    payload = {"rows": [{"name": "X", "phone": "13800009999"}]}
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=ops_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_requires_tenant_context(client: AsyncClient, ops_auth_headers):
    payload = {"rows": [{"name": "X", "phone": "13800009999"}]}
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=ops_auth_headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试，确认 FAIL（router 还不存在）**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_import.py -v 2>&1 | tail -15
```

期望：`ImportError` 或 `404` — 路由还不存在

- [ ] **Step 3: 创建 app/api/admin_cases.py，包含 import 端点**

创建 `poc/backend/app/api/admin_cases.py`：

```python
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_current_user,
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.case import (
    CaseAssignRequest,
    CaseAssignResponse,
    CaseImportRequest,
    CaseImportResponse,
    CaseStageUpdate,
    CaseWithOwnerResponse,
    OwnerInfo,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _require_tenant(payload: dict) -> int:
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _calc_priority(
    amount_owed: Optional[Decimal], months_overdue: Optional[int]
) -> int:
    return int(float(amount_owed or 0) * 0.4 + float(months_overdue or 0) * 0.3)


def _case_row_to_response(
    case: CollectionCase, owner: OwnerProfile
) -> CaseWithOwnerResponse:
    return CaseWithOwnerResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=mask_phone(owner.phone_enc),
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/cases/import", response_model=CaseImportResponse, status_code=201)
async def import_cases(
    body: CaseImportRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseImportResponse:
    tenant_id = _require_tenant(payload)
    imported = 0

    for row in body.rows:
        existing_owner = db.execute(
            select(OwnerProfile).where(
                OwnerProfile.tenant_id == tenant_id,
                OwnerProfile.phone_enc == row.phone,
            )
        ).scalar_one_or_none()

        if existing_owner is None:
            owner = OwnerProfile(
                tenant_id=tenant_id,
                name=row.name,
                phone_enc=row.phone,  # plaintext until AES sprint
                building=row.building,
                room=row.room,
            )
            db.add(owner)
            db.flush()
        else:
            owner = existing_owner

        case = CollectionCase(
            tenant_id=tenant_id,
            owner_id=owner.id,
            pool_type="public",
            stage="new",
            amount_owed=row.amount_owed,
            months_overdue=row.months_overdue,
            priority_score=_calc_priority(row.amount_owed, row.months_overdue),
        )
        db.add(case)
        imported += 1

    db.flush()
    db.commit()
    return CaseImportResponse(imported=imported, skipped=0, errors=[])
```

- [ ] **Step 4: 在 main.py 临时注册 admin_cases router（仅用于让测试能找到路由）**

打开 `poc/backend/app/main.py`，在 `from app.api import ...` 这行末尾加 `admin_cases`：

```python
from app.api import admin, admin_cases, auth, calls, devices, ops, recordings, tasks, users
```

在 `app.include_router(admin.router, ...)` 之后加：

```python
app.include_router(admin_cases.router, prefix="/api/v1/admin", tags=["admin-cases"])
```

- [ ] **Step 5: 运行 import 测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_import.py -v
```

期望：5 个测试全部 PASS

- [ ] **Step 6: commit**

```bash
git add app/api/admin_cases.py tests/api/test_admin_cases_import.py app/main.py
git commit -m "feat(admin): POST /admin/cases/import — JSON batch import with owner dedup"
```

---

## Task 4: GET /api/v1/admin/cases 列表 + GET /api/v1/admin/cases/{id} 详情（TDD）

**Files:**
- Modify: `poc/backend/app/api/admin_cases.py`
- Create: `poc/backend/tests/api/test_admin_cases_list.py`

- [ ] **Step 1: 写测试**

创建 `poc/backend/tests/api/test_admin_cases_list.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_cases_returns_seeded(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get("/api/v1/admin/cases", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_list_cases_filters_by_pool_type(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/admin/cases?pool_type=public", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["pool_type"] == "public"


@pytest.mark.asyncio
async def test_list_cases_filters_by_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/admin/cases?stage=new", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["stage"] == "new"


@pytest.mark.asyncio
async def test_list_cases_keyword_filter(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/admin/cases?keyword={seeded_owner.name}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_cases_includes_owner_info(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get("/api/v1/admin/cases", headers=admin_auth_headers)
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == seeded_case.id)
    assert item["owner"]["name"] == seeded_owner.name
    assert "****" in item["owner"]["phone_masked"]


@pytest.mark.asyncio
async def test_get_case_detail(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_case.id
    assert data["owner"]["name"] == seeded_owner.name


@pytest.mark.asyncio
async def test_get_case_detail_not_found(client: AsyncClient, admin_auth_headers):
    resp = await client.get("/api/v1/admin/cases/999999", headers=admin_auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/cases")
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试，确认 FAIL（端点还不存在）**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_list.py -v 2>&1 | tail -15
```

期望：`404` 或 `AttributeError`

- [ ] **Step 3: 在 admin_cases.py 末尾追加 list + detail 端点**

在 `poc/backend/app/api/admin_cases.py` 末尾（`import_cases` 函数之后）追加：

```python
@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: Optional[str] = Query(None),
    pool_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if keyword:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CollectionCase.priority_score.desc(), CollectionCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}", response_model=CaseWithOwnerResponse)
async def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseWithOwnerResponse:
    tenant_id = _require_tenant(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    return _case_row_to_response(row[0], row[1])
```

- [ ] **Step 4: 运行测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_list.py -v
```

期望：8 个测试全部 PASS

- [ ] **Step 5: 运行全部测试，确认无回归**

```bash
python -m pytest --tb=short -q
```

期望：全部 PASS

- [ ] **Step 6: commit**

```bash
git add app/api/admin_cases.py tests/api/test_admin_cases_list.py
git commit -m "feat(admin): GET /admin/cases list + GET /admin/cases/{id} detail with owner info"
```

---

## Task 5: POST /api/v1/admin/cases/assign + PATCH /api/v1/admin/cases/{id}/stage（TDD）

**Files:**
- Modify: `poc/backend/app/api/admin_cases.py`
- Create: `poc/backend/tests/api/test_admin_cases_actions.py`

- [ ] **Step 1: 写测试**

创建 `poc/backend/tests/api/test_admin_cases_actions.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_assign_cases_updates_assigned_to(
    client: AsyncClient,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_count"] == 1


@pytest.mark.asyncio
async def test_assign_cases_user_not_in_tenant(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": 999999},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_USER_NOT_IN_TENANT"


@pytest.mark.asyncio
async def test_assign_ignores_case_ids_from_other_tenant(
    client: AsyncClient,
    admin_auth_headers,
    seeded_member_user,
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [999998, 999999], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_update_stage_changes_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.patch(
        f"/api/v1/admin/cases/{seeded_case.id}/stage",
        json={"stage": "in_progress"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "in_progress"


@pytest.mark.asyncio
async def test_update_stage_rejects_invalid_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.patch(
        f"/api/v1/admin/cases/{seeded_case.id}/stage",
        json={"stage": "invalid_stage"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_stage_not_found(client: AsyncClient, admin_auth_headers):
    resp = await client.patch(
        "/api/v1/admin/cases/999999/stage",
        json={"stage": "paid"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_actions.py -v 2>&1 | tail -15
```

期望：`404` — 端点还不存在

- [ ] **Step 3: 在 admin_cases.py 末尾追加 assign + stage 端点**

注意：`assign` 端点路径 `/cases/assign` 必须在 `/cases/{case_id}` 之前注册，否则 FastAPI 会把 "assign" 当 case_id 处理。当前 `get_case` 已注册，需要确保 `assign_cases` 路由也在其之前。

在 `list_cases` 和 `get_case` 之间（即 `list_cases` 函数之后、`get_case` 函数之前）插入：

```python
@router.post("/cases/assign", response_model=CaseAssignResponse)
async def assign_cases(
    body: CaseAssignRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseAssignResponse:
    tenant_id = _require_tenant(payload)

    member = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == body.assign_to,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_USER_NOT_IN_TENANT", "message": "指定用户不在本租户"},
        )

    stmt = (
        update(CollectionCase)
        .where(
            CollectionCase.id.in_(body.case_ids),
            CollectionCase.tenant_id == tenant_id,
        )
        .values(assigned_to=body.assign_to, pool_type="private")
    )
    result = db.execute(stmt)
    db.commit()
    return CaseAssignResponse(updated_count=result.rowcount)
```

在 `get_case` 函数之后追加：

```python
@router.patch("/cases/{case_id}/stage", response_model=CaseResponse)
async def update_case_stage(
    case_id: int,
    body: CaseStageUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case.stage = body.stage
    db.commit()
    db.refresh(case)
    return case
```

同时在文件顶部 import 块加 `CaseResponse`（和已有的 `CaseWithOwnerResponse` 一起）：

```python
from app.schemas.case import (
    CaseAssignRequest,
    CaseAssignResponse,
    CaseImportRequest,
    CaseImportResponse,
    CaseResponse,
    CaseStageUpdate,
    CaseWithOwnerResponse,
    OwnerInfo,
)
```

- [ ] **Step 4: 运行测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_admin_cases_actions.py -v
```

期望：6 个测试全部 PASS

- [ ] **Step 5: 运行全部测试，确认无回归**

```bash
python -m pytest --tb=short -q
```

期望：全部 PASS

- [ ] **Step 6: commit**

```bash
git add app/api/admin_cases.py tests/api/test_admin_cases_actions.py
git commit -m "feat(admin): POST /admin/cases/assign + PATCH /admin/cases/{id}/stage"
```

---

## Task 6: GET /api/v1/supervisor/cases（TDD）

**Files:**
- Create: `poc/backend/app/api/supervisor.py`
- Create: `poc/backend/tests/api/test_supervisor_cases.py`

- [ ] **Step 1: 写测试**

创建 `poc/backend/tests/api/test_supervisor_cases.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_supervisor_can_see_all_tenant_cases(
    client: AsyncClient, supervisor_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_supervisor_cases_include_owner_info(
    client: AsyncClient, supervisor_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == seeded_case.id)
    assert item["owner"]["name"] == seeded_owner.name
    assert "****" in item["owner"]["phone_masked"]


@pytest.mark.asyncio
async def test_supervisor_filter_by_assigned_to(
    client: AsyncClient,
    supervisor_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # First assign the case
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    resp = await client.get(
        f"/api/v1/supervisor/cases?assigned_to={seeded_member_user.id}",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["assigned_to"] == seeded_member_user.id


@pytest.mark.asyncio
async def test_supervisor_requires_supervisor_role(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=admin_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_cases_pagination(
    client: AsyncClient, supervisor_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/supervisor/cases?page=1&page_size=5",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 5
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_supervisor_cases.py -v 2>&1 | tail -10
```

期望：`404` — router 未注册

- [ ] **Step 3: 创建 app/api/supervisor.py**

创建 `poc/backend/app/api/supervisor.py`：

```python
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import CaseWithOwnerResponse
from app.schemas.common import PaginatedResponse

from .admin_cases import _case_row_to_response, _require_tenant

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor",)


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: Optional[str] = Query(None),
    pool_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)
    # Supervisor sees all tenant cases; group-level scoping deferred to Sprint 3

    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if keyword:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CollectionCase.priority_score.desc(), CollectionCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 4: 在 main.py 注册 supervisor router**

打开 `poc/backend/app/main.py`，在 import 行加 `supervisor`：

```python
from app.api import admin, admin_cases, auth, calls, devices, ops, recordings, supervisor, tasks, users
```

在已有的 admin_cases router 之后加：

```python
app.include_router(supervisor.router, prefix="/api/v1/supervisor", tags=["supervisor"])
```

- [ ] **Step 5: 运行测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_supervisor_cases.py -v
```

期望：5 个测试全部 PASS

- [ ] **Step 6: commit**

```bash
git add app/api/supervisor.py tests/api/test_supervisor_cases.py app/main.py
git commit -m "feat(supervisor): GET /supervisor/cases — all tenant cases with filters"
```

---

## Task 7: GET /api/v1/agent/cases + POST /api/v1/agent/cases/{id}/claim（TDD）

**Files:**
- Create: `poc/backend/app/api/agent_cases.py`
- Create: `poc/backend/tests/api/test_agent_cases.py`

- [ ] **Step 1: 写测试**

创建 `poc/backend/tests/api/test_agent_cases.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_sees_public_unassigned_cases(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids  # seeded_case is public + unassigned


@pytest.mark.asyncio
async def test_agent_sees_own_private_cases(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign case to agent
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_claim_case_from_public_pool(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pool_type"] == "private"
    assert data["assigned_to"] is not None


@pytest.mark.asyncio
async def test_claim_already_claimed_case(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign to agent first
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    # Agent tries to claim an already assigned case
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_ALREADY_CLAIMED"


@pytest.mark.asyncio
async def test_claim_nonexistent_case(client: AsyncClient, agent_auth_headers):
    resp = await client.post(
        "/api/v1/agent/cases/999999/claim", headers=agent_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/agent/cases")
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_agent_cases.py -v 2>&1 | tail -10
```

期望：`404` — router 未注册

- [ ] **Step 3: 创建 app/api/agent_cases.py**

创建 `poc/backend/app/api/agent_cases.py`：

```python
from __future__ import annotations

from typing import Annotated, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import CaseResponse, CaseWithOwnerResponse
from app.schemas.common import PaginatedResponse

from .admin_cases import _case_row_to_response, _require_tenant

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_my_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    pool_type: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

    # Agent sees: their own private cases OR unassigned public pool cases
    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            sa.or_(
                CollectionCase.assigned_to == user.id,
                sa.and_(
                    CollectionCase.pool_type == "public",
                    CollectionCase.assigned_to.is_(None),
                ),
            ),
        )
    )
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(
            CollectionCase.assigned_to.desc().nulls_last(),
            CollectionCase.priority_score.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/cases/{case_id}/claim", response_model=CaseResponse)
async def claim_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.pool_type != "public" or case.assigned_to is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_CLAIMED", "message": "案件已被认领或不在公池"},
        )
    case.pool_type = "private"
    case.assigned_to = user.id
    db.commit()
    db.refresh(case)
    return case
```

- [ ] **Step 4: 在 main.py 注册 agent_cases router**

打开 `poc/backend/app/main.py`：

```python
from app.api import admin, admin_cases, agent_cases, auth, calls, devices, ops, recordings, supervisor, tasks, users
```

在 supervisor router 之后加：

```python
app.include_router(agent_cases.router, prefix="/api/v1/agent", tags=["agent"])
```

- [ ] **Step 5: 运行测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest tests/api/test_agent_cases.py -v
```

期望：6 个测试全部 PASS

- [ ] **Step 6: 运行全部测试**

```bash
python -m pytest --tb=short -q
```

期望：全部 PASS

- [ ] **Step 7: commit**

```bash
git add app/api/agent_cases.py tests/api/test_agent_cases.py app/main.py
git commit -m "feat(agent): GET /agent/cases + POST /agent/cases/{id}/claim"
```

---

## Task 8: 注册 routers（最终状态）+ 更新 nav.ts

**Files:**
- Modify: `poc/backend/app/main.py`（确认最终状态）
- Modify: `frontend/src/config/nav.ts`

- [ ] **Step 1: 确认 main.py 包含所有 Sprint 2 routers**

打开 `poc/backend/app/main.py`，确认完整状态如下：

```python
from app.api import admin, admin_cases, agent_cases, auth, calls, devices, ops, recordings, supervisor, tasks, users
```

以及 include_router 块：

```python
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(ops.router, prefix="/api/v1/ops", tags=["ops"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(admin_cases.router, prefix="/api/v1/admin", tags=["admin-cases"])
app.include_router(supervisor.router, prefix="/api/v1/supervisor", tags=["supervisor"])
app.include_router(agent_cases.router, prefix="/api/v1/agent", tags=["agent"])
# Legacy PoC routers (Sprint 1 migrates these to ORM + /api/v1/ prefix)
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["recordings"])
```

- [ ] **Step 2: 更新 frontend/src/config/nav.ts，加案件入口**

打开 `frontend/src/config/nav.ts`，将 `admin` / `supervisor` / `agent_internal` / `agent_external` 的配置更新如下（其余角色不变）：

```typescript
  admin: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "用户管理", path: "/admin/users" },
        { label: "案件管理", path: "/admin/cases" },
        { label: "导入案件", path: "/admin/cases/import" },
      ],
    },
  ],
  supervisor: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "案件总览", path: "/supervisor/cases" },
      ],
    },
  ],
  agent_internal: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
  agent_external: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
```

- [ ] **Step 3: 验证 TypeScript 无错误**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit 2>&1 | head -20
```

期望：无输出（无错误）

- [ ] **Step 4: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/main.py frontend/src/config/nav.ts
git commit -m "chore: finalize Sprint 2 router registrations + update nav.ts for admin/supervisor/agent roles"
```

---

## Task 9: 前端 — Admin 案件列表页（含分配弹窗）

**Files:**
- Create: `frontend/src/pages/admin/cases/index.tsx`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p /Users/shuo/AI/autoluyin/frontend/src/pages/admin/cases
```

- [ ] **Step 2: 写测试（TDD — 渲染测试）**

暂无独立测试文件（UI 页面通过 E2E 验证）；本步骤通过 TypeScript 编译和浏览器 smoke test 验收。

- [ ] **Step 3: 创建 frontend/src/pages/admin/cases/index.tsx**

```tsx
import { useCreate, useGo, useList } from "@refinedev/core";
import { Briefcase, Plus, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  status: string;
}

interface AgentItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待处理",
  in_progress: "处理中",
  promised: "已承诺",
  paid: "已缴费",
  escalated: "已上报",
  closed: "已关闭",
};

const POOL_LABELS: Record<string, string> = {
  public: "公池",
  private: "专属",
};

const STAGE_COLORS: Record<string, React.CSSProperties> = {
  new: { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  in_progress: { background: "var(--color-primary-light)", color: "var(--color-primary)" },
  promised: { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  paid: { background: "var(--color-success-light)", color: "var(--color-success)" },
  escalated: { background: "var(--color-danger-light)", color: "var(--color-danger)" },
  closed: { background: "var(--color-neutral-100)", color: "var(--color-neutral-400)" },
};

export function CaseListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [poolType, setPoolType] = useState("");
  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: Array<{ field: string; operator: string; value: unknown }> = [];
  if (keyword) filters.push({ field: "keyword", operator: "eq", value: keyword });
  if (poolType) filters.push({ field: "pool_type", operator: "eq", value: poolType });
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });

  const { query } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const { query: agentsQuery } = useList<AgentItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
    queryOptions: { enabled: assignModalOpen },
  });

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const rawAgents = agentsQuery.data?.data;
  const agents: AgentItem[] =
    (rawAgents as unknown as PaginatedResponse<AgentItem>)?.items ??
    (rawAgents as AgentItem[] | undefined) ??
    [];

  const { mutate: assignCases, isPending: assigning } = useCreate();

  function handleToggleSelect(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function handleAssign() {
    if (!selectedAgentId || selectedIds.length === 0) return;
    assignCases(
      {
        resource: "admin/cases/assign",
        values: { case_ids: selectedIds, assign_to: selectedAgentId },
      },
      {
        onSuccess: () => {
          setAssignModalOpen(false);
          setSelectedIds([]);
          setSelectedAgentId(null);
          query.refetch();
        },
      }
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            案件管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 件
          </span>
        </div>
        <div className="flex gap-2">
          {selectedIds.length > 0 && (
            <button
              type="button"
              onClick={() => setAssignModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium border border-[var(--color-primary)] text-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              <UserCheck className="w-4 h-4" />
              分配 ({selectedIds.length})
            </button>
          )}
          <button
            type="button"
            onClick={() => go({ to: "/admin/cases/import" })}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Plus className="w-4 h-4" />
            导入案件
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索业主姓名…"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] w-48"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
        <select
          value={poolType}
          onChange={(e) => {
            setPoolType(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部池</option>
          <option value="public">公池</option>
          <option value="private">专属</option>
        </select>
        <select
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部阶段</option>
          {Object.entries(STAGE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-3 py-3 w-8">
                <input
                  type="checkbox"
                  checked={
                    selectedIds.length === items.length && items.length > 0
                  }
                  onChange={(e) =>
                    setSelectedIds(
                      e.target.checked ? items.map((i) => i.id) : []
                    )
                  }
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                业主
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                房间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                欠费(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                逾期月数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                阶段
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                池
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无案件数据
                </td>
              </tr>
            )}
            {items.map((c) => (
              <tr
                key={c.id}
                className={`hover:bg-[var(--color-neutral-50)] ${
                  selectedIds.includes(c.id) ? "bg-blue-50" : ""
                }`}
              >
                <td className="px-3 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(c.id)}
                    onChange={() => handleToggleSelect(c.id)}
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--color-neutral-900)]">
                    {c.owner.name}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-400)]">
                    {c.owner.phone_masked}
                  </div>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.owner.building && c.owner.room
                    ? `${c.owner.building} ${c.owner.room}`
                    : (c.owner.building ?? c.owner.room ?? "—")}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_owed ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.months_overdue ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={STAGE_COLORS[c.stage] ?? {}}
                  >
                    {STAGE_LABELS[c.stage] ?? c.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {POOL_LABELS[c.pool_type] ?? c.pool_type}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/admin/cases/${c.id}` })}
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}

      {/* Assign Modal */}
      {assignModalOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div
            className="bg-white p-6 w-96 shadow-lg"
            style={{ borderRadius: "var(--radius-lg)" }}
          >
            <h2 className="text-lg font-semibold text-[var(--color-neutral-900)] mb-4">
              分配案件（共 {selectedIds.length} 件）
            </h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                选择催收员
              </label>
              <select
                value={selectedAgentId ?? ""}
                onChange={(e) =>
                  setSelectedAgentId(Number(e.target.value) || null)
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                <option value="">请选择</option>
                {agents
                  .filter((a) =>
                    ["agent_internal", "agent_external"].includes(a.role)
                  )
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}（{a.phone_masked}）
                    </option>
                  ))}
              </select>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setAssignModalOpen(false);
                  setSelectedAgentId(null);
                }}
                className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                取消
              </button>
              <button
                type="button"
                disabled={!selectedAgentId || assigning}
                onClick={handleAssign}
                className="px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                style={{
                  background: "var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                {assigning ? "分配中…" : "确认分配"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/admin/cases/index.tsx
git commit -m "feat(frontend): admin case list page with multi-select + assign modal"
```

---

## Task 10: 前端 — Admin 导入页 + Agent 案件页 + App.tsx 路由

**Files:**
- Create: `frontend/src/pages/admin/cases/import.tsx`
- Create: `frontend/src/pages/agent/cases/index.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 frontend/src/pages/admin/cases/import.tsx**

```tsx
import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft, Upload } from "lucide-react";
import { useState } from "react";

interface ImportRow {
  name: string;
  phone: string;
  building: string;
  room: string;
  amount_owed: string;
  months_overdue: string;
}

const EMPTY_ROW: ImportRow = {
  name: "",
  phone: "",
  building: "",
  room: "",
  amount_owed: "",
  months_overdue: "",
};

export function CaseImportPage() {
  const go = useGo();
  const [rows, setRows] = useState<ImportRow[]>([{ ...EMPTY_ROW }]);
  const [result, setResult] = useState<{
    imported: number;
    skipped: number;
    errors: string[];
  } | null>(null);

  const { mutate: importCases, isPending } = useCreate();

  function updateRow(idx: number, field: keyof ImportRow, value: string) {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r))
    );
  }

  function addRow() {
    setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  }

  function removeRow(idx: number) {
    setRows((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = rows
      .filter((r) => r.name && r.phone)
      .map((r) => ({
        name: r.name.trim(),
        phone: r.phone.trim(),
        building: r.building.trim() || null,
        room: r.room.trim() || null,
        amount_owed: r.amount_owed ? r.amount_owed.trim() : null,
        months_overdue: r.months_overdue
          ? parseInt(r.months_overdue, 10)
          : null,
      }));

    importCases(
      {
        resource: "admin/cases/import",
        values: { rows: payload },
      },
      {
        onSuccess: (data) => {
          const d = data.data as {
            imported: number;
            skipped: number;
            errors: string[];
          };
          setResult(d);
        },
      }
    );
  }

  if (result) {
    return (
      <div className="max-w-lg">
        <div
          className="p-6 bg-white border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <h2 className="text-lg font-semibold text-[var(--color-neutral-900)] mb-4">
            导入完成
          </h2>
          <div className="space-y-2 mb-6">
            <div className="flex justify-between text-sm">
              <span className="text-[var(--color-neutral-600)]">成功导入</span>
              <span
                className="font-medium"
                style={{ color: "var(--color-success)" }}
              >
                {result.imported} 件
              </span>
            </div>
            {result.skipped > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-[var(--color-neutral-600)]">跳过</span>
                <span
                  className="font-medium"
                  style={{ color: "var(--color-warning)" }}
                >
                  {result.skipped} 件
                </span>
              </div>
            )}
            {result.errors.length > 0 && (
              <div className="mt-3">
                <p
                  className="text-sm font-medium mb-1"
                  style={{ color: "var(--color-danger)" }}
                >
                  错误详情：
                </p>
                <ul className="text-xs space-y-0.5 text-[var(--color-neutral-600)]">
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setResult(null);
                setRows([{ ...EMPTY_ROW }]);
              }}
              className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              继续导入
            </button>
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases" })}
              className="px-4 py-2 text-sm font-medium text-white"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              查看案件列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <Upload className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            批量导入案件
          </h1>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="bg-white border border-[var(--color-neutral-200)] overflow-hidden mb-4">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  姓名 *
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  手机号 *
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  楼栋
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  房间
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  欠费金额
                </th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                  逾期月数
                </th>
                <th className="px-3 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {rows.map((row, idx) => (
                <tr key={idx}>
                  {(
                    [
                      "name",
                      "phone",
                      "building",
                      "room",
                      "amount_owed",
                      "months_overdue",
                    ] as (keyof ImportRow)[]
                  ).map((field) => (
                    <td key={field} className="px-3 py-2">
                      <input
                        type={
                          field === "amount_owed" || field === "months_overdue"
                            ? "number"
                            : "text"
                        }
                        value={row[field]}
                        onChange={(e) => updateRow(idx, field, e.target.value)}
                        className="w-full px-2 py-1 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                        style={{ borderRadius: "var(--radius-sm)" }}
                        placeholder={
                          field === "name"
                            ? "张三"
                            : field === "phone"
                              ? "138xxxx"
                              : ""
                        }
                      />
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => removeRow(idx)}
                      disabled={rows.length === 1}
                      className="text-[var(--color-danger)] disabled:opacity-30 text-xs"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={addRow}
            className="text-sm text-[var(--color-primary)] hover:underline"
          >
            + 添加一行
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases" })}
              className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isPending || rows.filter((r) => r.name && r.phone).length === 0}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              {isPending ? "导入中…" : `导入 ${rows.filter((r) => r.name && r.phone).length} 条`}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: 创建 frontend/src/pages/agent/cases/ 目录和页面**

```bash
mkdir -p /Users/shuo/AI/autoluyin/frontend/src/pages/agent/cases
```

创建 `frontend/src/pages/agent/cases/index.tsx`：

```tsx
import { useCreate, useList } from "@refinedev/core";
import { Phone } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待处理",
  in_progress: "处理中",
  promised: "已承诺",
  paid: "已缴费",
  escalated: "已上报",
  closed: "已关闭",
};

const STAGE_COLORS: Record<string, React.CSSProperties> = {
  new: { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  in_progress: { background: "var(--color-primary-light)", color: "var(--color-primary)" },
  promised: { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  paid: { background: "var(--color-success-light)", color: "var(--color-success)" },
  escalated: { background: "var(--color-danger-light)", color: "var(--color-danger)" },
  closed: { background: "var(--color-neutral-100)", color: "var(--color-neutral-400)" },
};

export function AgentCaseListPage() {
  const [page, setPage] = useState(1);
  const [stage, setStage] = useState("");
  const [poolType, setPoolType] = useState("");
  const [claimingId, setClaimingId] = useState<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: Array<{ field: string; operator: string; value: unknown }> = [];
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });
  if (poolType) filters.push({ field: "pool_type", operator: "eq", value: poolType });

  const { query } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const { mutate: claimCase } = useCreate();

  function handleClaim(caseId: number) {
    setClaimingId(caseId);
    claimCase(
      {
        resource: `agent/cases/${caseId}/claim`,
        values: {},
      },
      {
        onSuccess: () => {
          setClaimingId(null);
          query.refetch();
        },
        onError: () => {
          setClaimingId(null);
        },
      }
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Phone className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            我的案件
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 件
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={poolType}
          onChange={(e) => {
            setPoolType(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部（公池+专属）</option>
          <option value="public">公池</option>
          <option value="private">我的专属</option>
        </select>
        <select
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部阶段</option>
          {Object.entries(STAGE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                业主
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                房间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                欠费(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                逾期月数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                阶段
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                来源
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无案件
                </td>
              </tr>
            )}
            {items.map((c) => (
              <tr
                key={c.id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--color-neutral-900)]">
                    {c.owner.name}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-400)]">
                    {c.owner.phone_masked}
                  </div>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.owner.building && c.owner.room
                    ? `${c.owner.building} ${c.owner.room}`
                    : (c.owner.building ?? c.owner.room ?? "—")}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_owed ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.months_overdue ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={STAGE_COLORS[c.stage] ?? {}}
                  >
                    {STAGE_LABELS[c.stage] ?? c.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {c.pool_type === "public" ? "公池" : "专属"}
                </td>
                <td className="px-4 py-3">
                  {c.pool_type === "public" && c.assigned_to === null ? (
                    <button
                      type="button"
                      disabled={claimingId === c.id}
                      onClick={() => handleClaim(c.id)}
                      className="text-xs font-medium text-white px-2 py-1 disabled:opacity-40"
                      style={{
                        background: "var(--color-primary)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      {claimingId === c.id ? "认领中…" : "认领"}
                    </button>
                  ) : (
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {c.assigned_to !== null ? "已认领" : "—"}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 更新 frontend/src/App.tsx**

打开 `frontend/src/App.tsx`，在 import 块加三个新页面：

```tsx
import { CaseListPage } from "./pages/admin/cases/index";
import { CaseImportPage } from "./pages/admin/cases/import";
import { AgentCaseListPage } from "./pages/agent/cases/index";
```

在 `resources` 数组加两个新 resource（在已有的 `admin/users` 之后）：

```tsx
          {
            name: "admin/cases",
            list: "/admin/cases",
            create: "/admin/cases/import",
          },
          {
            name: "agent/cases",
            list: "/agent/cases",
          },
```

在 `</Route>` 保护路由块内（在 `/admin/users/new` 之后）加三个新路由：

```tsx
            {/* Admin - Case Management */}
            <Route path="/admin/cases" element={<CaseListPage />} />
            <Route path="/admin/cases/import" element={<CaseImportPage />} />
            {/* Agent - Case List */}
            <Route path="/agent/cases" element={<AgentCaseListPage />} />
```

- [ ] **Step 4: TypeScript 编译检查**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit 2>&1 | head -30
```

期望：无输出（无错误）

- [ ] **Step 5: 构建检查**

```bash
npm run build 2>&1 | tail -20
```

期望：Build 成功，无 TS 错误

- [ ] **Step 6: 运行全部后端测试，确认无回归**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -m pytest --tb=short -q
```

期望：全部 PASS

- [ ] **Step 7: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/admin/cases/ frontend/src/pages/agent/ frontend/src/App.tsx
git commit -m "feat(frontend): admin case import page + agent cases page + App.tsx routing"
```

---

## Sprint 2 验收标准

### 后端
- `python -m pytest --tb=short -q` 全部 PASS（Sprint 1 原有 + Sprint 2 新增共约 60+ 测试）
- `POST /api/v1/admin/cases/import` 支持批量导入，重复手机号复用 OwnerProfile
- `GET /api/v1/admin/cases` 返回分页 + owner 信息（手机号脱敏）
- `POST /api/v1/admin/cases/assign` 批量分配，越权 case_id 被忽略
- `PATCH /api/v1/admin/cases/{id}/stage` 阶段跃迁受 Literal 限制
- `GET /api/v1/supervisor/cases` 只有 supervisor 角色可访问
- `POST /api/v1/agent/cases/{id}/claim` 正确切换 pool_type=private + assigned_to

### 前端
- `npm run build` 无 TS 错误
- `/admin/cases`：能显示案件列表、筛选器、多选复选框、分配弹窗
- `/admin/cases/import`：能添加行、提交后显示导入结果
- `/agent/cases`：能显示公池案件、认领按钮状态正确
- Sidebar 中 admin / supervisor / agent 角色导航菜单更新
