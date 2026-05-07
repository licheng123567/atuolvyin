# Sprint 1: 用户身份端点 + 租户管理 + 用户管理 + 角色动态导航 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `GET /api/v1/users/me`、platform_ops 租户 CRUD、admin 用户管理，以及前端角色动态侧边栏导航，完成 Sprint 0 之后的第一个功能闭环。

**Architecture:** 后端新增三个 APIRouter（users / ops / admin），全部通过 `require_roles` 鉴权；前端增加 `src/config/nav.ts` 角色导航配置，Sidebar 根据当前用户 role 动态渲染菜单，租户/用户管理页面使用 Refine `useList / useCreate / useOne / useUpdate`。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 / pytest+httpx+testcontainers · TypeScript / React / Refine v5 / shadcn/ui / Tailwind CSS / lucide-react

---

## File Map

| 操作 | 路径 | 说明 |
|------|------|------|
| Modify | `poc/backend/app/core/security.py` | 加 `mask_phone()` |
| Modify | `poc/backend/app/schemas/user.py` | 加 `UserMeResponse` |
| Create | `poc/backend/app/schemas/tenant.py` | Tenant CRUD schemas |
| Create | `poc/backend/app/api/users.py` | `GET /api/v1/users/me` |
| Create | `poc/backend/app/api/ops.py` | Tenant CRUD for platform_ops |
| Create | `poc/backend/app/api/admin.py` | User mgmt for admin role |
| Modify | `poc/backend/app/main.py` | 注册三个新 router |
| Modify | `poc/backend/tests/conftest.py` | 加 `seeded_tenant` / `auth_token` / `auth_headers` fixtures |
| Create | `poc/backend/tests/api/test_users_me.py` | GET /me 测试 |
| Create | `poc/backend/tests/api/test_ops_tenants.py` | Tenant CRUD 测试 |
| Create | `poc/backend/tests/api/test_admin_users.py` | User mgmt 测试 |
| Create | `frontend/src/config/nav.ts` | 角色导航配置 |
| Modify | `frontend/src/components/layout/Sidebar.tsx` | 动态导航渲染 |
| Create | `frontend/src/pages/ops/tenants/index.tsx` | 租户列表 |
| Create | `frontend/src/pages/ops/tenants/new.tsx` | 新建租户 |
| Create | `frontend/src/pages/ops/tenants/[id].tsx` | 租户详情 + 配额 |
| Create | `frontend/src/pages/admin/users/index.tsx` | 用户列表 |
| Create | `frontend/src/pages/admin/users/new.tsx` | 新建内部用户 |
| Modify | `frontend/src/App.tsx` | 增加路由 + Refine resources |

---

## Task 1: Auth fixtures + GET /api/v1/users/me

**Files:**
- Modify: `poc/backend/app/core/security.py`
- Modify: `poc/backend/app/schemas/user.py`
- Create: `poc/backend/app/api/users.py`
- Modify: `poc/backend/tests/conftest.py`
- Create: `poc/backend/tests/api/test_users_me.py`

- [ ] **Step 1: 在 security.py 末尾加 `mask_phone`**

在 `poc/backend/app/core/security.py` 末尾追加：

```python
def mask_phone(phone: str) -> str:
    """Return 138****1234 format. Input is plaintext 11-digit phone."""
    if len(phone) == 11:
        return phone[:3] + "****" + phone[7:]
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else "***"
```

- [ ] **Step 2: 在 schemas/user.py 加 `UserMeResponse`**

在 `poc/backend/app/schemas/user.py` 的 import 块加 `Optional`（已有），然后在文件末尾追加：

```python
class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    tenant_id: Optional[int]
    scope: str
```

- [ ] **Step 3: 写测试（先写，确保 FAIL）**

创建 `poc/backend/tests/api/test_users_me.py`：

```python
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.fixture
def ops_token():
    return create_access_token({
        "sub": "1",
        "user_id": 1,
        "tenant_id": None,
        "role": "platform_ops",
        "scope": "platform",
    })


@pytest.fixture
def ops_headers(ops_token):
    return {"Authorization": f"Bearer {ops_token}"}


@pytest.mark.asyncio
async def test_get_me_returns_identity(client: AsyncClient, seeded_user, ops_headers):
    resp = await client.get("/api/v1/users/me", headers=ops_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_user.id
    assert data["name"] == seeded_user.name
    assert data["role"] == "platform_ops"
    assert data["tenant_id"] is None
    assert data["scope"] == "platform"


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 4: 在 conftest.py 加 `seeded_user` fixture**

在 `poc/backend/tests/conftest.py` 末尾追加（在 `client` fixture 之后）：

```python
from app.core.security import get_password_hash
from app.models.user import UserAccount


@pytest.fixture
def seeded_user(db_session):
    user = UserAccount(
        phone_enc="13800138001",
        name="测试用户",
        password_hash=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user
```

- [ ] **Step 5: 运行测试，确认 FAIL（路由不存在）**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_users_me.py -v 2>&1 | head -30
```

预期：`404` or `ImportError: cannot import name 'users'` 之类报错

- [ ] **Step 6: 创建 `poc/backend/app/api/users.py`**

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, get_token_payload
from app.models.user import UserAccount
from app.schemas.user import UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(get_current_user)],
) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        name=user.name,
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id"),
        scope=payload.get("scope", ""),
    )
```

- [ ] **Step 7: 在 main.py 注册 users router**

在 `poc/backend/app/main.py` 的 import 行加 `users`：
```python
from app.api import auth, calls, devices, recordings, tasks, users
```

在 `app.include_router(auth.router, ...)` 下方加：
```python
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
```

- [ ] **Step 8: 运行测试，确认全部 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_users_me.py -v
```

预期：3 tests PASS

- [ ] **Step 9: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/core/security.py app/schemas/user.py app/api/users.py app/main.py tests/conftest.py tests/api/test_users_me.py
git commit -m "feat: add GET /api/v1/users/me endpoint with mask_phone helper"
```

---

## Task 2: 角色动态侧边栏导航

**Files:**
- Create: `frontend/src/config/nav.ts`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: 创建 `frontend/src/config/nav.ts`**

```typescript
import type { UserRole } from "../types";

export interface NavItem {
  label: string;
  path: string;
  icon?: string; // lucide icon name — resolved in Sidebar
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

const NAV_CONFIG: Partial<Record<UserRole, NavSection[]>> = {
  platform_superadmin: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants" },
      ],
    },
  ],
  platform_ops: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants" },
      ],
    },
  ],
  admin: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "用户管理", path: "/admin/users" },
      ],
    },
  ],
  supervisor: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  agent_internal: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  agent_external: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  legal: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  workorder: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  project_manager_property: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  project_manager_provider: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
  provider_admin: [
    {
      items: [
        { label: "控制台", path: "/" },
      ],
    },
  ],
};

export function getNavSections(role: UserRole | string): NavSection[] {
  return NAV_CONFIG[role as UserRole] ?? [{ items: [{ label: "控制台", path: "/" }] }];
}
```

- [ ] **Step 2: 更新 `frontend/src/components/layout/Sidebar.tsx`**

完整替换为：

```typescript
import { useGetIdentity, useLogout } from "@refinedev/core";
import { Home, Building2, Users, LogOut } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
import { getNavSections } from "../../config/nav";
import { cn } from "../../lib/utils";

const ROLE_LABELS: Record<string, string> = {
  platform_superadmin: "平台超管",
  platform_ops: "平台运营员",
  provider_admin: "服务商管理员",
  admin: "物业管理员",
  supervisor: "主管/督导",
  agent_internal: "催收员（内部）",
  agent_external: "催收员（兼职）",
  legal: "法务专员",
  workorder: "工单处理员",
  project_manager_property: "项目负责人（物业）",
  project_manager_provider: "项目负责人（服务商）",
};

const ICON_MAP: Record<string, React.ElementType> = {
  "/": Home,
  "/ops/tenants": Building2,
  "/admin/users": Users,
};

export function Sidebar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const { mutate: logout } = useLogout();
  const location = useLocation();

  const initials = user?.name?.slice(0, 1) ?? "?";
  const sections = user ? getNavSections(user.role) : [];

  return (
    <aside
      className="flex flex-col bg-white border-r border-[var(--color-neutral-200)] flex-shrink-0"
      style={{ width: "var(--sidebar-width)" }}
    >
      {/* Logo row */}
      <div
        className="flex items-center px-5 border-b border-[var(--color-neutral-200)] flex-shrink-0"
        style={{ height: "var(--topbar-height)" }}
      >
        <span className="text-base font-bold text-[var(--color-primary)]">
          有证慧催
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {sections.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p className="px-3 mb-1 text-xs font-medium text-[var(--color-neutral-400)] uppercase tracking-wider">
                {section.title}
              </p>
            )}
            {section.items.map((item) => {
              const Icon = ICON_MAP[item.path] ?? Home;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors",
                    isActive
                      ? "bg-[var(--color-primary)] text-white font-medium"
                      : "text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]",
                  )}
                  style={{ borderRadius: "var(--radius-md)" }}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User block + logout */}
      <div className="border-t border-[var(--color-neutral-200)] p-3">
        {user && (
          <div className="flex items-center gap-2 px-2 py-1 mb-1">
            <div
              className="flex-shrink-0 flex items-center justify-center rounded-full text-white text-xs font-semibold"
              style={{ width: 28, height: 28, background: "var(--color-primary)" }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--color-neutral-900)] truncate">
                {user.name}
              </p>
              <p className="text-xs text-[var(--color-neutral-400)] truncate">
                {ROLE_LABELS[user.role] ?? user.role}
              </p>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => logout()}
          className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded transition-colors text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-100)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          退出登录
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: 确认前端编译无报错**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npm run build 2>&1 | tail -20
```

预期：无 TypeScript 错误，`dist/` 生成成功

- [ ] **Step 4: Commit**

```bash
cd /Users/shuo/AI/autoluyin/frontend
git add src/config/nav.ts src/components/layout/Sidebar.tsx
git commit -m "feat: add role-based dynamic sidebar navigation"
```

---

## Task 3: 租户 schemas

**Files:**
- Create: `poc/backend/app/schemas/tenant.py`

- [ ] **Step 1: 创建 `poc/backend/app/schemas/tenant.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    credit_code: Optional[str] = Field(None, max_length=50)
    admin_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    plan: str = Field("trial", pattern=r"^(trial|standard|premium)$")
    monthly_minute_quota: Optional[int] = Field(None, ge=0, le=100000)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("租户名称不能为空")
        return v


class TenantQuotaUpdate(BaseModel):
    monthly_minute_quota: int = Field(..., ge=0, le=100000)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    credit_code: Optional[str]
    admin_phone_masked: str  # computed by service layer
    plan: str
    monthly_minute_quota: Optional[int]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
```

- [ ] **Step 2: 确认 schema 可导入（语法检查）**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -c "from app.schemas.tenant import TenantCreate, TenantResponse, TenantQuotaUpdate; print('OK')"
```

预期：`OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/schemas/tenant.py
git commit -m "feat: add tenant CRUD schemas (TenantCreate/Response/QuotaUpdate)"
```

---

## Task 4: 租户列表端点（GET /api/v1/ops/tenants）

**Files:**
- Create: `poc/backend/app/api/ops.py` (初始版本，仅 list)
- Modify: `poc/backend/app/main.py`
- Create: `poc/backend/tests/api/test_ops_tenants.py` (仅 list 测试)
- Modify: `poc/backend/tests/conftest.py` (加 `seeded_tenant` + `ops_auth_headers`)

- [ ] **Step 1: 在 conftest.py 加 `seeded_tenant` 和 `ops_auth_headers`**

在 `poc/backend/tests/conftest.py` 的 `seeded_user` fixture 之后追加：

```python
from app.models.tenant import Tenant, UserTenantMembership


@pytest.fixture
def seeded_tenant(db_session):
    tenant = Tenant(
        name="测试物业公司",
        admin_phone_enc="13900139001",
        plan="trial",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.flush()
    return tenant


@pytest.fixture
def ops_auth_headers(seeded_user):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": None,
        "role": "platform_ops",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(seeded_user, seeded_tenant, db_session):
    from app.core.security import create_access_token
    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="admin",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "admin",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: 写 list 测试（先写，确认 FAIL）**

创建 `poc/backend/tests/api/test_ops_tenants.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tenants_returns_paginated(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get("/api/v1/ops/tenants", headers=ops_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(t["id"] == seeded_tenant.id for t in data["items"])


@pytest.mark.asyncio
async def test_list_tenants_requires_ops_role(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get("/api/v1/ops/tenants", headers=admin_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_tenants_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/ops/tenants")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_tenants_search_by_name(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/tenants",
        params={"q": "测试物业"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["id"] == seeded_tenant.id for t in data["items"])


@pytest.mark.asyncio
async def test_list_tenants_search_no_match(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/tenants",
        params={"q": "绝对不存在的名字xyz"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
```

- [ ] **Step 3: 运行测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_ops_tenants.py -v 2>&1 | head -20
```

预期：404 或 ImportError

- [ ] **Step 4: 创建 `poc/backend/app/api/ops.py`（仅 list）**

```python
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import mask_phone, require_roles
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.tenant import TenantResponse

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_superadmin")


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        credit_code=tenant.credit_code,
        admin_phone_masked=mask_phone(tenant.admin_phone_enc),
        plan=tenant.plan,
        monthly_minute_quota=tenant.monthly_minute_quota,
        expires_at=tenant.expires_at,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.get("/tenants", response_model=PaginatedResponse[TenantResponse])
async def list_tenants(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[TenantResponse]:
    stmt = select(Tenant)
    if q:
        stmt = stmt.where(Tenant.name.ilike(f"%{q}%"))
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(total_stmt).scalar_one()
    tenants = db.execute(
        stmt.order_by(Tenant.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return PaginatedResponse(
        items=[_tenant_to_response(t) for t in tenants],
        total=total,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 5: 在 main.py 注册 ops router**

在 `poc/backend/app/main.py` import 行加 `ops`：
```python
from app.api import auth, calls, devices, ops, recordings, tasks, users
```

在 `app.include_router(users.router, ...)` 下方加：
```python
app.include_router(ops.router, prefix="/api/v1/ops", tags=["ops"])
```

- [ ] **Step 6: 运行测试，确认 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_ops_tenants.py::test_list_tenants_returns_paginated tests/api/test_ops_tenants.py::test_list_tenants_requires_ops_role tests/api/test_ops_tenants.py::test_list_tenants_requires_auth tests/api/test_ops_tenants.py::test_list_tenants_search_by_name tests/api/test_ops_tenants.py::test_list_tenants_search_no_match -v
```

预期：5 tests PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/api/ops.py app/main.py tests/conftest.py tests/api/test_ops_tenants.py
git commit -m "feat: add GET /api/v1/ops/tenants list endpoint with search and pagination"
```

---

## Task 5: 租户创建端点（POST /api/v1/ops/tenants）

**Files:**
- Modify: `poc/backend/app/api/ops.py`
- Modify: `poc/backend/tests/api/test_ops_tenants.py`

- [ ] **Step 1: 在 test_ops_tenants.py 末尾追加创建相关测试**

```python
@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient, ops_auth_headers):
    payload = {
        "name": "新物业公司",
        "admin_phone": "13700137001",
        "plan": "standard",
        "monthly_minute_quota": 500,
    }
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "新物业公司"
    assert data["plan"] == "standard"
    assert data["monthly_minute_quota"] == 500
    assert data["admin_phone_masked"] == "137****7001"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_tenant_invalid_phone(client: AsyncClient, ops_auth_headers):
    payload = {"name": "X公司", "admin_phone": "12345", "plan": "trial"}
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_duplicate_credit_code(
    client: AsyncClient, seeded_tenant, ops_auth_headers, db_session
):
    from app.models.tenant import Tenant
    seeded_tenant.credit_code = "91110000000000001X"
    db_session.flush()

    payload = {
        "name": "另一家公司",
        "admin_phone": "13600136001",
        "plan": "trial",
        "credit_code": "91110000000000001X",
    }
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_CREDIT_CODE"
```

- [ ] **Step 2: 运行新测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_ops_tenants.py::test_create_tenant_success -v 2>&1 | head -15
```

预期：404 或 405

- [ ] **Step 3: 在 ops.py 加 create endpoint**

在 `_tenant_to_response` 函数之后、`list_tenants` 之前加：

```python
from fastapi import status as http_status
from sqlalchemy.exc import IntegrityError

from app.schemas.tenant import TenantCreate, TenantQuotaUpdate
```

在 `list_tenants` 之后追加：

```python
@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = Tenant(
        name=body.name,
        credit_code=body.credit_code,
        admin_phone_enc=body.admin_phone,  # plaintext until AES sprint
        plan=body.plan,
        monthly_minute_quota=body.monthly_minute_quota,
        is_active=True,
    )
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_DUPLICATE_CREDIT_CODE",
                "message": "统一社会信用代码已存在",
            },
        )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)
```

Add `from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status` and `from sqlalchemy.exc import IntegrityError` to ops.py imports.

The full updated imports block for `ops.py`:

```python
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import mask_phone, require_roles
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.tenant import TenantCreate, TenantQuotaUpdate, TenantResponse
```

- [ ] **Step 4: 运行所有 ops 测试，确认 PASS**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_ops_tenants.py -v
```

预期：8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/api/ops.py tests/api/test_ops_tenants.py
git commit -m "feat: add POST /api/v1/ops/tenants create endpoint"
```

---

## Task 6: 租户详情 + 配额更新（GET + PATCH /api/v1/ops/tenants/{id}）

**Files:**
- Modify: `poc/backend/app/api/ops.py`
- Modify: `poc/backend/tests/api/test_ops_tenants.py`

- [ ] **Step 1: 在 test_ops_tenants.py 末尾追加详情/配额测试**

```python
@pytest.mark.asyncio
async def test_get_tenant_by_id(client: AsyncClient, seeded_tenant, ops_auth_headers):
    resp = await client.get(
        f"/api/v1/ops/tenants/{seeded_tenant.id}", headers=ops_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_tenant.id
    assert data["name"] == seeded_tenant.name


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient, ops_auth_headers):
    resp = await client.get("/api/v1/ops/tenants/99999999", headers=ops_auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_quota(client: AsyncClient, seeded_tenant, ops_auth_headers):
    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/quota",
        json={"monthly_minute_quota": 1000},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["monthly_minute_quota"] == 1000


@pytest.mark.asyncio
async def test_update_quota_negative(client: AsyncClient, seeded_tenant, ops_auth_headers):
    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/quota",
        json={"monthly_minute_quota": -1},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: 在 ops.py 末尾追加 get_tenant + update_quota**

```python
@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    return _tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/quota", response_model=TenantResponse)
async def update_tenant_quota(
    tenant_id: int,
    body: TenantQuotaUpdate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    from datetime import datetime, timezone

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    tenant.monthly_minute_quota = body.monthly_minute_quota
    tenant.minute_quota_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)
```

- [ ] **Step 3: 运行全部 ops 测试**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_ops_tenants.py -v
```

预期：12 tests PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/api/ops.py tests/api/test_ops_tenants.py
git commit -m "feat: add GET/PATCH /api/v1/ops/tenants/{id} detail and quota endpoints"
```

---

## Task 7: 前端租户管理页面

**Files:**
- Create: `frontend/src/pages/ops/tenants/index.tsx`
- Create: `frontend/src/pages/ops/tenants/new.tsx`
- Create: `frontend/src/pages/ops/tenants/[id].tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建租户列表页 `frontend/src/pages/ops/tenants/index.tsx`**

```typescript
import { useList, useNavigation } from "@refinedev/core";
import { Building2, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface TenantItem {
  id: number;
  name: string;
  plan: string;
  monthly_minute_quota: number | null;
  admin_phone_masked: string;
  is_active: boolean;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: "试用",
  standard: "标准版",
  premium: "高级版",
};

export function TenantListPage() {
  const { push } = useNavigation();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading } = useList<TenantItem>({
    resource: "ops/tenants",
    pagination: { current: page, pageSize: PAGE_SIZE },
    filters: q ? [{ field: "q", operator: "eq", value: q }] : [],
  });

  const items = (data?.data as unknown as PaginatedResponse<TenantItem>)?.items ?? (data?.data as TenantItem[] | undefined) ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            租户管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 家
          </span>
        </div>
        <button
          type="button"
          onClick={() => push("/ops/tenants/new")}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white transition-colors"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新建租户
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          placeholder="搜索租户名称…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          className="w-full pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">租户名称</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">管理员手机</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">套餐</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">月配额（分钟）</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">状态</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  暂无租户数据
                </td>
              </tr>
            )}
            {items.map((t) => (
              <tr key={t.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {t.name}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {t.admin_phone_masked}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {PLAN_LABELS[t.plan] ?? t.plan}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {t.monthly_minute_quota ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${
                      t.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-600"
                    }`}
                  >
                    {t.is_active ? "正常" : "停用"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => push(`/ops/tenants/${t.id}`)}
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
    </div>
  );
}
```

- [ ] **Step 2: 创建新建租户页 `frontend/src/pages/ops/tenants/new.tsx`**

```typescript
import { useCreate, useNavigation } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

interface FormData {
  name: string;
  admin_phone: string;
  credit_code: string;
  plan: string;
  monthly_minute_quota: string;
}

export function TenantNewPage() {
  const { push } = useNavigation();
  const { mutate: create, isPending } = useCreate();
  const [form, setForm] = useState<FormData>({
    name: "",
    admin_phone: "",
    credit_code: "",
    plan: "trial",
    monthly_minute_quota: "",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleChange = (field: keyof FormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    create(
      {
        resource: "ops/tenants",
        values: {
          name: form.name,
          admin_phone: form.admin_phone,
          credit_code: form.credit_code || undefined,
          plan: form.plan,
          monthly_minute_quota: form.monthly_minute_quota
            ? Number(form.monthly_minute_quota)
            : undefined,
        },
      },
      {
        onSuccess: () => push("/ops/tenants"),
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "创建失败，请重试");
        },
      }
    );
  };

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => push("/ops/tenants")}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新建租户
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        {[
          { label: "租户名称 *", field: "name" as const, type: "text", placeholder: "例：XX物业管理有限公司", required: true },
          { label: "管理员手机 *", field: "admin_phone" as const, type: "tel", placeholder: "138xxxxxxxx", required: true },
          { label: "统一社会信用代码", field: "credit_code" as const, type: "text", placeholder: "选填", required: false },
          { label: "月配额（分钟）", field: "monthly_minute_quota" as const, type: "number", placeholder: "留空表示不限", required: false },
        ].map(({ label, field, type, placeholder, required }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              {label}
            </label>
            <input
              type={type}
              value={form[field]}
              onChange={handleChange(field)}
              placeholder={placeholder}
              required={required}
              min={type === "number" ? 0 : undefined}
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        ))}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            套餐
          </label>
          <select
            value={form.plan}
            onChange={handleChange("plan")}
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="trial">试用</option>
            <option value="standard">标准版</option>
            <option value="premium">高级版</option>
          </select>
        </div>

        {errorMsg && (
          <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending}
            className="flex-1 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "提交中…" : "创建租户"}
          </button>
          <button
            type="button"
            onClick={() => push("/ops/tenants")}
            className="px-4 py-2 text-sm border border-[var(--color-neutral-200)] rounded text-[var(--color-neutral-600)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: 创建租户详情页 `frontend/src/pages/ops/tenants/[id].tsx`**

```typescript
import { useOne, useUpdate, useNavigation } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

interface TenantDetail {
  id: number;
  name: string;
  credit_code: string | null;
  admin_phone_masked: string;
  plan: string;
  monthly_minute_quota: number | null;
  is_active: boolean;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: "试用",
  standard: "标准版",
  premium: "高级版",
};

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { push } = useNavigation();
  const { data, isLoading } = useOne<TenantDetail>({
    resource: "ops/tenants",
    id: id ?? "",
  });
  const { mutate: update, isPending } = useUpdate();

  const [quota, setQuota] = useState("");
  const [quotaMsg, setQuotaMsg] = useState("");

  const tenant = data?.data;

  const handleQuotaSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setQuotaMsg("");
    update(
      {
        resource: `ops/tenants/${id}/quota`,
        id: "",
        values: { monthly_minute_quota: Number(quota) },
      },
      {
        onSuccess: () => {
          setQuotaMsg("配额已更新");
          setQuota("");
        },
        onError: (err) => {
          const e = err as { message?: string };
          setQuotaMsg(e.message ?? "更新失败");
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--color-neutral-400)]">加载中…</div>
    );
  }
  if (!tenant) {
    return (
      <div className="text-sm text-[var(--color-danger)]">租户不存在</div>
    );
  }

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => push("/ops/tenants")}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          {tenant.name}
        </h1>
      </div>

      {/* Info card */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 mb-4">
        <h2 className="text-sm font-semibold text-[var(--color-neutral-700)] mb-4">
          基本信息
        </h2>
        <dl className="space-y-3 text-sm">
          {[
            ["套餐", PLAN_LABELS[tenant.plan] ?? tenant.plan],
            ["管理员手机", tenant.admin_phone_masked],
            ["社会信用代码", tenant.credit_code ?? "—"],
            ["状态", tenant.is_active ? "正常" : "停用"],
            ["月配额（分钟）", tenant.monthly_minute_quota?.toString() ?? "不限"],
            ["创建时间", new Date(tenant.created_at).toLocaleDateString("zh-CN")],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt className="text-[var(--color-neutral-500)]">{k}</dt>
              <dd className="font-medium text-[var(--color-neutral-900)]">{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Quota update */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6">
        <h2 className="text-sm font-semibold text-[var(--color-neutral-700)] mb-4">
          更新月配额
        </h2>
        <form onSubmit={handleQuotaSubmit} className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
              新配额（分钟）
            </label>
            <input
              type="number"
              min={0}
              max={100000}
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
              placeholder="输入分钟数"
              required
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <button
            type="submit"
            disabled={isPending || !quota}
            className="px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "更新中…" : "确认"}
          </button>
        </form>
        {quotaMsg && (
          <p className="text-xs mt-2 text-[var(--color-neutral-600)]">{quotaMsg}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 在 App.tsx 注册 ops 路由 + Refine resources**

完整替换 `frontend/src/App.tsx`：

```typescript
import { Authenticated, Refine } from "@refinedev/core";
import routerBindings from "@refinedev/react-router";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/login";
import { TenantListPage } from "./pages/ops/tenants/index";
import { TenantNewPage } from "./pages/ops/tenants/new";
import { TenantDetailPage } from "./pages/ops/tenants/[id]";
import { authProvider } from "./providers/auth-provider";
import { dataProvider } from "./providers";

function App() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        routerProvider={routerBindings}
        resources={[
          {
            name: "ops/tenants",
            list: "/ops/tenants",
            create: "/ops/tenants/new",
            show: "/ops/tenants/:id",
          },
        ]}
        options={{ syncWithLocation: true, warnWhenUnsavedChanges: false }}
      >
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected — wrapped in layout shell */}
          <Route
            element={
              <Authenticated
                key="app"
                fallback={<Navigate to="/login" replace />}
              >
                <AppLayout>
                  <Outlet />
                </AppLayout>
              </Authenticated>
            }
          >
            <Route
              path="/"
              element={
                <div className="text-[var(--color-neutral-900)]">
                  <h1 className="text-2xl font-semibold mb-2">欢迎使用有证慧催</h1>
                  <p className="text-sm text-[var(--color-neutral-600)]">
                    请从左侧菜单进入各功能模块。
                  </p>
                </div>
              }
            />
            {/* Ops - Tenant Management */}
            <Route path="/ops/tenants" element={<TenantListPage />} />
            <Route path="/ops/tenants/new" element={<TenantNewPage />} />
            <Route path="/ops/tenants/:id" element={<TenantDetailPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
```

- [ ] **Step 5: 确认编译通过**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npm run build 2>&1 | tail -20
```

预期：`dist/` 生成，无 TypeScript 错误

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin/frontend
git add src/pages/ops/ src/App.tsx
git commit -m "feat: add tenant management pages (list/new/detail) with Refine integration"
```

---

## Task 8: 用户管理 schemas + admin router + GET /api/v1/admin/users

**Files:**
- Modify: `poc/backend/app/schemas/user.py` (add `UserListResponse` + `UserCreateByAdminRequest`)
- Create: `poc/backend/app/api/admin.py`
- Modify: `poc/backend/app/main.py`
- Create: `poc/backend/tests/api/test_admin_users.py`
- Modify: `poc/backend/tests/conftest.py` (add `seeded_member_user`)

- [ ] **Step 1: 在 schemas/user.py 追加新 schemas**

在 `poc/backend/app/schemas/user.py` 的 `InviteLinkResponse` 之后追加：

```python
class UserCreateByAdminRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    password: str = Field(..., min_length=8, max_length=72)
    role: str = Field(
        ...,
        pattern=r"^(supervisor|agent_internal|legal|workorder|project_manager_property)$",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str
    role: str
    is_active: bool
    created_at: datetime
```

- [ ] **Step 2: 在 conftest.py 追加 `seeded_member_user` fixture**

在 `poc/backend/tests/conftest.py` 的 `admin_auth_headers` fixture 之后追加：

```python
@pytest.fixture
def seeded_member_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    user = UserAccount(
        phone_enc="13811138111",
        name="催收员小王",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_internal",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user
```

- [ ] **Step 3: 写 test_admin_users.py（先写，确认 FAIL）**

创建 `poc/backend/tests/api/test_admin_users.py`：

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_returns_tenant_members(
    client: AsyncClient,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/users", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert any(u["id"] == seeded_member_user.id for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_requires_admin_role(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/admin/users", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_users_masks_phone(
    client: AsyncClient,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/users", headers=admin_auth_headers)
    items = resp.json()["items"]
    member = next(u for u in items if u["id"] == seeded_member_user.id)
    assert "****" in member["phone_masked"]
    assert member["phone_masked"] == "138****8111"
```

- [ ] **Step 4: 运行测试，确认 FAIL**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_admin_users.py -v 2>&1 | head -20
```

- [ ] **Step 5: 创建 `poc/backend/app/api/admin.py`（仅 list）**

```python
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import mask_phone, require_roles
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserListResponse

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _user_to_response(user: UserAccount, role: str) -> UserListResponse:
    return UserListResponse(
        id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    current_user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    payload: Annotated[dict, Depends(lambda: None)],  # replaced below
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserListResponse]:
    # Get tenant_id from token payload via separate dep
    raise NotImplementedError
```

Wait — `require_roles` returns the `UserAccount` but I also need `tenant_id` from the payload to filter by tenant. Let me restructure to get payload properly.

Replace the whole `admin.py` with:

```python
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_current_user,
    get_password_hash,
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserListResponse

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _user_to_response(user: UserAccount, role: str) -> UserListResponse:
    return UserListResponse(
        id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserListResponse]:
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    stmt = (
        select(UserAccount, UserTenantMembership.role)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    )
    if q:
        stmt = stmt.where(UserAccount.name.ilike(f"%{q}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(UserAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_user_to_response(user, role) for user, role in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 6: 在 main.py 注册 admin router**

在 `poc/backend/app/main.py` import 行加 `admin`：
```python
from app.api import admin, auth, calls, devices, ops, recordings, tasks, users
```

在 `app.include_router(ops.router, ...)` 下方加：
```python
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
```

- [ ] **Step 7: 运行 list 相关测试**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_admin_users.py::test_list_users_returns_tenant_members tests/api/test_admin_users.py::test_list_users_requires_admin_role tests/api/test_admin_users.py::test_list_users_requires_auth tests/api/test_admin_users.py::test_list_users_masks_phone -v
```

预期：4 tests PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/schemas/user.py app/api/admin.py app/main.py tests/conftest.py tests/api/test_admin_users.py
git commit -m "feat: add GET /api/v1/admin/users list with tenant isolation and phone masking"
```

---

## Task 9: POST /admin/users 创建内部用户 + POST /admin/users/invite

**Files:**
- Modify: `poc/backend/app/api/admin.py`
- Modify: `poc/backend/tests/api/test_admin_users.py`

- [ ] **Step 1: 追加 create user + invite 测试**

在 `poc/backend/tests/api/test_admin_users.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_create_internal_user(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {
        "name": "督导赵六",
        "phone": "13500135005",
        "password": "Secure@1234",
        "role": "supervisor",
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "督导赵六"
    assert data["role"] == "supervisor"
    assert "****" in data["phone_masked"]


@pytest.mark.asyncio
async def test_create_user_duplicate_phone(
    client: AsyncClient, seeded_tenant, seeded_member_user, admin_auth_headers
):
    payload = {
        "name": "重复手机用户",
        "phone": "13811138111",  # same as seeded_member_user
        "password": "Secure@1234",
        "role": "supervisor",
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_PHONE"


@pytest.mark.asyncio
async def test_create_user_invalid_role(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {
        "name": "超管尝试",
        "phone": "13500135006",
        "password": "Secure@1234",
        "role": "platform_superadmin",  # not allowed for admin
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_invite_link(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {"role": "agent_external", "quota": 30, "expire_days": 7}
    resp = await client.post(
        "/api/v1/admin/users/invite", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert "url" in data
    assert "expires_at" in data
```

- [ ] **Step 2: 在 admin.py 追加 create + invite endpoints**

在 `poc/backend/app/api/admin.py` 的 import 末尾追加所需依赖：
```python
from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy.exc import IntegrityError
from app.schemas.user import InviteLinkRequest, InviteLinkResponse, UserCreateByAdminRequest, UserResponse
```

**注意**：`UserResponse` 的 `phone_masked` 字段需要 service 层计算，所以在 admin.py 里 create 端点返回时手动构建。

在 `list_users` 之后追加：

```python
@router.post("/users", response_model=UserListResponse, status_code=201)
async def create_user(
    body: UserCreateByAdminRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    new_user = UserAccount(
        phone_enc=body.phone,  # plaintext until AES sprint
        name=body.name,
        password_hash=get_password_hash(body.password),
        is_active=True,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_DUPLICATE_PHONE", "message": "手机号已被注册"},
        )

    membership = UserTenantMembership(
        user_id=new_user.id,
        tenant_id=tenant_id,
        role=body.role,
        source_type="INTERNAL",
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)
    return _user_to_response(new_user, body.role)


@router.post("/users/invite", response_model=InviteLinkResponse, status_code=201)
async def generate_invite_link(
    body: InviteLinkRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
) -> InviteLinkResponse:
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.expire_days)
    # Invite token storage deferred to Sprint 2 (need invite_token table)
    return InviteLinkResponse(
        token=token,
        url=f"/register?token={token}",
        expires_at=expires_at,
    )
```

Also add `from sqlalchemy.exc import IntegrityError` and `import secrets` and `from datetime import datetime, timedelta, timezone` to the imports at the top of `admin.py`.

- [ ] **Step 3: 运行全部 admin 测试**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/api/test_admin_users.py -v
```

预期：8 tests PASS

- [ ] **Step 4: 运行所有后端测试，确认无回归**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

预期：所有 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
git add app/api/admin.py tests/api/test_admin_users.py
git commit -m "feat: add POST /api/v1/admin/users create user and invite link endpoints"
```

---

## Task 10: 前端用户管理页面 + 路由接入

**Files:**
- Create: `frontend/src/pages/admin/users/index.tsx`
- Create: `frontend/src/pages/admin/users/new.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建用户列表页 `frontend/src/pages/admin/users/index.tsx`**

```typescript
import { useList, useNavigation } from "@refinedev/core";
import { Users, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface UserItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  supervisor: "主管/督导",
  agent_internal: "催收员（内部）",
  agent_external: "催收员（兼职）",
  legal: "法务专员",
  workorder: "工单处理员",
  project_manager_property: "项目负责人（物业）",
};

export function UserListPage() {
  const { push } = useNavigation();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading } = useList<UserItem>({
    resource: "admin/users",
    pagination: { current: page, pageSize: PAGE_SIZE },
    filters: q ? [{ field: "q", operator: "eq", value: q }] : [],
  });

  const items = (data?.data as unknown as PaginatedResponse<UserItem>)?.items ?? (data?.data as UserItem[] | undefined) ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            用户管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 人
          </span>
        </div>
        <button
          type="button"
          onClick={() => push("/admin/users/new")}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white transition-colors"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新建用户
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          placeholder="搜索用户姓名…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          className="w-full pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">姓名</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">手机</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">角色</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">状态</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  暂无用户
                </td>
              </tr>
            )}
            {items.map((u) => (
              <tr key={u.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {u.name}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {u.phone_masked}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {ROLE_LABELS[u.role] ?? u.role}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${
                      u.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-600"
                    }`}
                  >
                    {u.is_active ? "正常" : "停用"}
                  </span>
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

- [ ] **Step 2: 创建新建用户页 `frontend/src/pages/admin/users/new.tsx`**

```typescript
import { useCreate, useNavigation } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

interface FormData {
  name: string;
  phone: string;
  password: string;
  role: string;
}

const ALLOWED_ROLES = [
  { value: "supervisor", label: "主管/督导" },
  { value: "agent_internal", label: "催收员（内部）" },
  { value: "legal", label: "法务专员" },
  { value: "workorder", label: "工单处理员" },
  { value: "project_manager_property", label: "项目负责人（物业）" },
];

export function UserNewPage() {
  const { push } = useNavigation();
  const { mutate: create, isPending } = useCreate();
  const [form, setForm] = useState<FormData>({
    name: "",
    phone: "",
    password: "",
    role: "agent_internal",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleChange = (field: keyof FormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    create(
      {
        resource: "admin/users",
        values: form,
      },
      {
        onSuccess: () => push("/admin/users"),
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "创建失败，请重试");
        },
      }
    );
  };

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => push("/admin/users")}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新建内部用户
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        {[
          { label: "姓名 *", field: "name" as const, type: "text", placeholder: "真实姓名", required: true },
          { label: "手机号 *", field: "phone" as const, type: "tel", placeholder: "138xxxxxxxx", required: true },
          { label: "初始密码 *", field: "password" as const, type: "password", placeholder: "至少8位", required: true },
        ].map(({ label, field, type, placeholder, required }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              {label}
            </label>
            <input
              type={type}
              value={form[field]}
              onChange={handleChange(field)}
              placeholder={placeholder}
              required={required}
              minLength={field === "password" ? 8 : undefined}
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        ))}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            角色 *
          </label>
          <select
            value={form.role}
            onChange={handleChange("role")}
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            {ALLOWED_ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        {errorMsg && (
          <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending}
            className="flex-1 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "提交中…" : "创建用户"}
          </button>
          <button
            type="button"
            onClick={() => push("/admin/users")}
            className="px-4 py-2 text-sm border border-[var(--color-neutral-200)] rounded text-[var(--color-neutral-600)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: 在 App.tsx 加 admin 路由和 resource**

在 `frontend/src/App.tsx` 的 import 区加：
```typescript
import { UserListPage } from "./pages/admin/users/index";
import { UserNewPage } from "./pages/admin/users/new";
```

在 `resources` 数组加：
```typescript
{
  name: "admin/users",
  list: "/admin/users",
  create: "/admin/users/new",
},
```

在 Route 区段（`/ops/tenants/:id` 之后）加：
```typescript
{/* Admin - User Management */}
<Route path="/admin/users" element={<UserListPage />} />
<Route path="/admin/users/new" element={<UserNewPage />} />
```

- [ ] **Step 4: 最终前端编译检查**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npm run build 2>&1 | tail -20
```

预期：无 TypeScript 错误，构建成功

- [ ] **Step 5: 运行全部后端测试做最终验证**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python3.12 -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

预期：全部 PASS，无回归

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin/frontend
git add src/pages/admin/ src/App.tsx
git commit -m "feat: add admin user management pages (list/new) and route wiring"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ GET /api/v1/users/me → Task 1
- ✅ 租户列表 + 搜索 → Task 4
- ✅ 租户创建 → Task 5
- ✅ 租户详情 + 配额更新 → Task 6
- ✅ 角色动态导航 → Task 2
- ✅ 用户列表（租户隔离）→ Task 8
- ✅ 创建内部用户 → Task 9
- ✅ 邀请链接生成 → Task 9
- ✅ 前端租户管理三页 → Task 7
- ✅ 前端用户管理两页 → Task 10
- ✅ 所有后端端点有 TDD → Tasks 1/4/5/6/8/9
- ✅ 手机号脱敏（mask_phone）→ Task 1 + applied in all responses
- ✅ 多租户隔离（tenant_id from JWT payload）→ Tasks 8/9

**约束遵守：**
- ✅ `require_roles` 鉴权覆盖所有端点
- ✅ `PaginatedResponse` 泛型用于所有列表
- ✅ 错误响应格式 `{"code": "ERR_XXX", "message": "..."}`
- ✅ 前端无 `any` 类型（使用具体 interface）
- ✅ 图标只用 lucide-react
- ✅ 组件用 Tailwind + CSS variables，无新颜色

**已知延期项（不属于 Sprint 1）：**
- 手机号 AES-256 存储加密（注释中已标注，Sprint 2/3 专项）
- 邀请 token 持久化到数据库（InviteLinkResponse 已返回 token，存储待 Sprint 2）
- Sidebar 中 `/provider_admin`、`/legal` 等角色的详细导航菜单（各角色 Sprint 实现时补充）
