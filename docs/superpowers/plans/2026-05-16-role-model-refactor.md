# 角色模型重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把角色从一维字符串模型重构为「平台身份 + 组织职能 + 组织归属 + 工作方式」四维正交模型,角色枚举收敛为 6 个组织职能角色 + 2 个平台角色,并加 DB CHECK 约束。

**Architecture:** 平台身份落到 `UserAccount.platform_role`;组织职能角色 `UserTenantMembership.role` 收敛为 6 个;组织归属由已有的 `provider_id` 表达(删除冗余的 `source_type`);催收员工作方式落到新列 `work_mode`。后端新增 `app/core/roles.py` 作为角色常量单一事实源;登录身份解析三处重复代码合并到 `app/core/identity.py`。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL(后端);React + Refine.dev + TypeScript(前端);Kotlin(Android);pytest + testcontainers(测试)。

**分支:** `feature/role-model-refactor`(已建)。所有 commit 落在此分支。

**前置:** Docker 栈在跑(`cd poc && docker compose up -d`)。后端容器名 `autoluyin-backend`。

---

## 角色映射总表(全程引用)

| 旧值(role 字符串) | 新 `role` | 新 `work_mode` | 新 `platform_role` | 备注 |
|---|---|---|---|---|
| `admin` | `admin` | — | — | provider_id 不变 |
| `provider_admin` | `admin` | — | — | provider_id 不变(非空) |
| `supervisor` | `supervisor` | — | — | |
| `agent_internal` | `agent` | `internal` | — | |
| `agent_external` | `agent` | `external` | — | |
| `legal` | `legal` | — | — | |
| `coordinator` | `coordinator` | — | — | |
| `project_manager_property` | `project_manager` | — | — | |
| `project_manager_provider` | `project_manager` | — | — | provider_id 不变(非空) |
| `property_manager_property` | `project_manager` | — | — | 历史拼写变体 |
| `property_manager_provider` | `project_manager` | — | — | 历史拼写变体 |
| `platform_ops`(membership) | 删除该 membership 行 | — | account `platform_role='ops'` | |
| `platform_superadmin` / `platform_super`(membership) | 删除该 membership 行 | — | account `platform_role='superadmin'` | |
| 无 membership 的账号 | — | — | account `platform_role='superadmin'` | 一次性修复 |

最终合法值域:
- `UserTenantMembership.role` ∈ `{admin, project_manager, supervisor, agent, legal, coordinator}`
- `UserTenantMembership.work_mode` ∈ `{internal, external}` 或 `NULL`(非空当且仅当 `role='agent'`)
- `UserAccount.platform_role` ∈ `{superadmin, ops}` 或 `NULL`

---

## Task 1:后端角色常量单一事实源 `app/core/roles.py`

**Files:**
- Create: `poc/backend/app/core/roles.py`
- Test: `poc/backend/tests/test_roles_constants.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/test_roles_constants.py
from app.core import roles


def test_org_roles_are_the_six_functional_roles():
    assert roles.ORG_ROLES == frozenset(
        {"admin", "project_manager", "supervisor", "agent", "legal", "coordinator"}
    )


def test_platform_roles():
    assert roles.PLATFORM_ROLES == frozenset({"superadmin", "ops"})


def test_work_modes():
    assert roles.WORK_MODES == frozenset({"internal", "external"})


def test_legacy_role_map_covers_all_old_values():
    # 每个旧值都映射到一个合法新组织角色
    for old, new in roles.LEGACY_ROLE_MAP.items():
        assert new in roles.ORG_ROLES, f"{old} -> {new} 不是合法组织角色"


def test_constants_are_uppercase_module_level():
    assert isinstance(roles.ROLE_ADMIN, str) and roles.ROLE_ADMIN == "admin"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec autoluyin-backend pytest tests/test_roles_constants.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.roles'`

- [ ] **Step 3: 写实现**

```python
# poc/backend/app/core/roles.py
"""角色模型单一事实源(v2.2 角色重构)。

禁止在其他文件再散落角色字符串字面量 —— 一律从这里 import。

四个维度:
- 平台身份  UserAccount.platform_role  ∈ PLATFORM_ROLES | None
- 组织职能  UserTenantMembership.role  ∈ ORG_ROLES
- 组织归属  UserTenantMembership.provider_id  None=物业侧 / int=服务商侧
- 工作方式  UserTenantMembership.work_mode  ∈ WORK_MODES | None(仅 agent)
"""
from __future__ import annotations

# ─── 组织职能角色 ──────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_PROJECT_MANAGER = "project_manager"
ROLE_SUPERVISOR = "supervisor"
ROLE_AGENT = "agent"
ROLE_LEGAL = "legal"
ROLE_COORDINATOR = "coordinator"

ORG_ROLES = frozenset(
    {ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, ROLE_AGENT, ROLE_LEGAL, ROLE_COORDINATOR}
)

# ─── 平台身份 ─────────────────────────────────────────────────
PLATFORM_SUPERADMIN = "superadmin"
PLATFORM_OPS = "ops"
PLATFORM_ROLES = frozenset({PLATFORM_SUPERADMIN, PLATFORM_OPS})

# ─── 工作方式(仅 agent)──────────────────────────────────────
WORK_INTERNAL = "internal"
WORK_EXTERNAL = "external"
WORK_MODES = frozenset({WORK_INTERNAL, WORK_EXTERNAL})

# ─── 旧值 → 新值映射(迁移 + seed + 测试共用)────────────────
LEGACY_ROLE_MAP: dict[str, str] = {
    "admin": ROLE_ADMIN,
    "provider_admin": ROLE_ADMIN,
    "supervisor": ROLE_SUPERVISOR,
    "agent_internal": ROLE_AGENT,
    "agent_external": ROLE_AGENT,
    "legal": ROLE_LEGAL,
    "coordinator": ROLE_COORDINATOR,
    "project_manager_property": ROLE_PROJECT_MANAGER,
    "project_manager_provider": ROLE_PROJECT_MANAGER,
    "property_manager_property": ROLE_PROJECT_MANAGER,
    "property_manager_provider": ROLE_PROJECT_MANAGER,
}

# 旧 agent 角色 → work_mode
LEGACY_WORK_MODE_MAP: dict[str, str] = {
    "agent_internal": WORK_INTERNAL,
    "agent_external": WORK_EXTERNAL,
}

# 旧平台 membership.role → platform_role
LEGACY_PLATFORM_ROLE_MAP: dict[str, str] = {
    "platform_ops": PLATFORM_OPS,
    "platform_superadmin": PLATFORM_SUPERADMIN,
    "platform_super": PLATFORM_SUPERADMIN,
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec autoluyin-backend pytest tests/test_roles_constants.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add poc/backend/app/core/roles.py poc/backend/tests/test_roles_constants.py
git commit -m "feat: 新增角色常量单一事实源 app/core/roles.py"
```

---

## Task 2:ORM 模型 + Alembic 迁移(原子提交)

**Files:**
- Modify: `poc/backend/app/models/user.py:13-30`(`UserAccount`)
- Modify: `poc/backend/app/models/tenant.py:107-127`(`UserTenantMembership`)
- Create: `poc/backend/alembic/versions/24015_v220_role_model_refactor.py`
- Test: `poc/backend/tests/test_role_migration.py`

> 注:ORM 模型与 DB schema 必须同一 commit 落地 —— 任一单独提交都会造成模型/schema 不一致(ORM SELECT 引用不存在的列即报错)。本任务只在 Step 7 提交一次。

- [ ] **Step 1: `UserAccount` 加 `platform_role` 列**

在 `poc/backend/app/models/user.py` 的 `UserAccount` 类中,`preferences` 字段后追加:

```python
    # v2.2 角色重构 — 平台身份(superadmin / ops),非平台用户为 NULL
    platform_role: Mapped[str | None] = mapped_column(sa.String(16))
```

- [ ] **Step 2: `UserTenantMembership` 加 `work_mode`、删 `source_type`**

在 `poc/backend/app/models/tenant.py` 的 `UserTenantMembership` 类中:

删除这一行(第 118 行):
```python
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="INTERNAL")
```

在 `provider_id` 字段后追加:
```python
    # v2.2 角色重构 — 催收员工作方式;非空当且仅当 role='agent'
    work_mode: Mapped[str | None] = mapped_column(sa.String(16))
```

- [ ] **Step 3: 写迁移文件**

```python
# poc/backend/alembic/versions/24015_v220_role_model_refactor.py
"""v2.2 — 角色模型重构:platform_role / work_mode / 删 source_type / CHECK 约束

Revision ID: 24015v220
Revises: 24014v210
Create Date: 2026-05-16 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24015v220"
down_revision: str | None = "24014v210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_CK = "ck_membership_role"
_PLATFORM_CK = "ck_account_platform_role"
_WORK_MODE_CK = "ck_membership_work_mode"


def upgrade() -> None:
    # 1. 加新列(先可空,回填后再加约束)
    op.add_column("user_account", sa.Column("platform_role", sa.String(16), nullable=True))
    op.add_column(
        "user_tenant_membership", sa.Column("work_mode", sa.String(16), nullable=True)
    )

    # 2. 回填 work_mode(必须在 role 改值之前 —— 依赖旧 agent_* 值)
    op.execute(
        "UPDATE user_tenant_membership SET work_mode='internal' WHERE role='agent_internal'"
    )
    op.execute(
        "UPDATE user_tenant_membership SET work_mode='external' WHERE role='agent_external'"
    )

    # 3. 回填 platform_role(从平台 membership 推),然后删除这些平台 membership 行
    op.execute(
        """
        UPDATE user_account SET platform_role='ops' WHERE id IN (
            SELECT user_id FROM user_tenant_membership WHERE role='platform_ops'
        )
        """
    )
    op.execute(
        """
        UPDATE user_account SET platform_role='superadmin' WHERE id IN (
            SELECT user_id FROM user_tenant_membership
            WHERE role IN ('platform_superadmin','platform_super')
        )
        """
    )
    op.execute(
        "DELETE FROM user_tenant_membership "
        "WHERE role IN ('platform_ops','platform_superadmin','platform_super')"
    )
    # 无任何 membership 的账号 → 一次性判定为 superadmin
    op.execute(
        """
        UPDATE user_account SET platform_role='superadmin'
        WHERE platform_role IS NULL
          AND id NOT IN (SELECT DISTINCT user_id FROM user_tenant_membership)
        """
    )

    # 4. 收敛 role(顺序无关 —— 每条 UPDATE 命中互斥的旧值集合)
    op.execute("UPDATE user_tenant_membership SET role='admin' WHERE role='provider_admin'")
    op.execute("UPDATE user_tenant_membership SET role='agent' WHERE role IN ('agent_internal','agent_external')")
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager' "
        "WHERE role IN ('project_manager_property','project_manager_provider',"
        "'property_manager_property','property_manager_provider')"
    )

    # 5. 删冗余列 source_type
    op.drop_column("user_tenant_membership", "source_type")

    # 6. 加 CHECK 约束
    op.create_check_constraint(
        _ROLE_CK,
        "user_tenant_membership",
        "role IN ('admin','project_manager','supervisor','agent','legal','coordinator')",
    )
    op.create_check_constraint(
        _PLATFORM_CK,
        "user_account",
        "platform_role IS NULL OR platform_role IN ('superadmin','ops')",
    )
    op.create_check_constraint(
        _WORK_MODE_CK,
        "user_tenant_membership",
        "(role = 'agent') = (work_mode IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_WORK_MODE_CK, "user_tenant_membership", type_="check")
    op.drop_constraint(_PLATFORM_CK, "user_account", type_="check")
    op.drop_constraint(_ROLE_CK, "user_tenant_membership", type_="check")

    # 重建 source_type,按 provider_id 回填
    op.add_column(
        "user_tenant_membership",
        sa.Column("source_type", sa.Text(), nullable=False, server_default="INTERNAL"),
    )
    op.execute(
        "UPDATE user_tenant_membership SET source_type='PROVIDER' WHERE provider_id IS NOT NULL"
    )
    op.alter_column("user_tenant_membership", "source_type", server_default=None)

    # role 反映射(注意:provider_admin/agent_internal 等区分信息靠 provider_id/work_mode)
    op.execute(
        "UPDATE user_tenant_membership SET role='provider_admin' "
        "WHERE role='admin' AND provider_id IS NOT NULL"
    )
    op.execute("UPDATE user_tenant_membership SET role='agent_internal' WHERE work_mode='internal'")
    op.execute("UPDATE user_tenant_membership SET role='agent_external' WHERE work_mode='external'")
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager_provider' "
        "WHERE role='project_manager' AND provider_id IS NOT NULL"
    )
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager_property' "
        "WHERE role='project_manager' AND provider_id IS NULL"
    )

    # 平台账号还原一条 membership 不可靠(原 tenant_id 已丢失)—— downgrade 仅恢复列结构,
    # 平台角色还原需重跑 seed。删列即可。
    op.drop_column("user_tenant_membership", "work_mode")
    op.drop_column("user_account", "platform_role")
```

- [ ] **Step 4: 跑迁移**

Run: `docker exec autoluyin-backend alembic upgrade head`
Expected: 末行 `Running upgrade 24014v210 -> 24015v220`,无报错

- [ ] **Step 5: 写约束测试**

```python
# poc/backend/tests/test_role_migration.py
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_role_check_rejects_legacy_value(db_session):
    """迁移后非法旧角色值被 CHECK 拒绝。"""
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO user_tenant_membership (user_id, tenant_id, role, is_active) "
                "VALUES (1, 1, 'provider_admin', true)"
            )
        )
        db_session.flush()


def test_work_mode_check_requires_agent(db_session):
    """work_mode 非空但 role 不是 agent → 被拒。"""
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO user_tenant_membership (user_id, tenant_id, role, work_mode, is_active) "
                "VALUES (1, 1, 'supervisor', 'internal', true)"
            )
        )
        db_session.flush()


def test_platform_role_check_rejects_unknown(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO user_account (phone_enc, name, password_hash, platform_role) "
                 "VALUES ('x', 'x', 'x', 'god')")
        )
        db_session.flush()


def test_source_type_column_dropped(db_session):
    cols = db_session.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name='user_tenant_membership'")
    ).scalars().all()
    assert "source_type" not in cols
    assert "work_mode" in cols
```

> `db_session` fixture 来自 `tests/conftest.py`(testcontainers-postgres session)。若该 fixture 名不同,用 `conftest.py` 中实际的 DB session fixture 名替换。

- [ ] **Step 6: 跑约束测试 + 验证模型导入**

Run: `docker exec autoluyin-backend pytest tests/test_role_migration.py -v`
Expected: PASS(4 passed)

Run: `docker exec autoluyin-backend python -c "from app.models.user import UserAccount; from app.models.tenant import UserTenantMembership; print('ok', hasattr(UserAccount,'platform_role'), hasattr(UserTenantMembership,'work_mode'), not hasattr(UserTenantMembership,'source_type'))"`
Expected: `ok True True True`

- [ ] **Step 7: Commit**

```bash
git add poc/backend/app/models/user.py poc/backend/app/models/tenant.py poc/backend/alembic/versions/24015_v220_role_model_refactor.py poc/backend/tests/test_role_migration.py
git commit -m "feat: 角色模型重构 — ORM + 迁移(加列/回填/删 source_type/CHECK)"
```

---

## Task 3:登录身份解析合并到 `app/core/identity.py`(DRY + 修 scope/超管隐患)

**Files:**
- Create: `poc/backend/app/core/identity.py`
- Modify: `poc/backend/app/api/auth.py:22-101`
- Modify: `poc/backend/app/api/auth_extras.py:45`(`ADMIN_LIKE_ROLES`)、`142-197`(`_issue_token`)、`520-596`(`select_membership`)
- Test: `poc/backend/tests/test_identity_resolution.py`

> 现状:`auth.py::login`、`auth_extras._issue_token`、`auth_extras.select_membership` 三处重复了「查 membership → 算 role/scope/provider_id」的逻辑,且都把无 membership 默认成超管。本任务抽成一个函数。

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/test_identity_resolution.py
import pytest
from fastapi import HTTPException

from app.core.identity import resolve_identity


def test_platform_role_takes_precedence(db_session, make_user):
    user = make_user(platform_role="superadmin")
    claims = resolve_identity(db_session, user)
    assert claims.role == "superadmin"
    assert claims.scope == "platform"
    assert claims.tenant_id is None


def test_provider_membership_scope_is_provider(db_session, make_user, make_membership):
    user = make_user()
    make_membership(user, role="admin", provider_id=1)
    claims = resolve_identity(db_session, user)
    assert claims.scope == "provider:1"


def test_tenant_membership_scope_is_tenant(db_session, make_user, make_membership):
    user = make_user()
    m = make_membership(user, role="supervisor", provider_id=None)
    claims = resolve_identity(db_session, user)
    assert claims.scope == f"tenant:{m.tenant_id}"


def test_no_role_no_membership_rejected(db_session, make_user):
    """无 platform_role 且无 membership → 不再默认超管,拒绝登录。"""
    user = make_user(platform_role=None)
    with pytest.raises(HTTPException) as exc:
        resolve_identity(db_session, user)
    assert exc.value.status_code == 403
```

> `make_user` / `make_membership` 是测试工厂 fixture。若 `conftest.py` 无此类工厂,在 `tests/test_identity_resolution.py` 顶部用 `@pytest.fixture` 就地定义:`make_user` 插入 `UserAccount`,`make_membership` 插入 `UserTenantMembership` 并返回对象。

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec autoluyin-backend pytest tests/test_identity_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.identity'`

- [ ] **Step 3: 写 `identity.py`**

```python
# poc/backend/app/core/identity.py
"""登录身份解析(v2.2 角色重构)。

合并原先散在 auth.py / auth_extras.py 的三处重复逻辑。
平台身份(UserAccount.platform_role)优先;否则取组织 membership。
无平台身份且无 membership → 拒绝(不再默认超管)。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount


@dataclass(frozen=True)
class IdentityClaims:
    role: str
    scope: str  # 'platform' | 'tenant:{id}' | 'provider:{id}'
    tenant_id: int | None
    provider_id: int | None
    tenant_name: str | None


def resolve_identity(
    db: Session,
    user: UserAccount,
    membership: UserTenantMembership | None = None,
) -> IdentityClaims:
    """算出登录后写进 JWT 的身份声明。

    membership 显式传入时(如 select-membership 切换角色)直接用它;
    否则取该用户第一条有效 membership。
    """
    # 1. 平台身份优先
    if user.platform_role:
        return IdentityClaims(
            role=user.platform_role,
            scope="platform",
            tenant_id=None,
            provider_id=None,
            tenant_name=None,
        )

    # 2. 组织 membership
    if membership is None:
        membership = db.execute(
            select(UserTenantMembership)
            .where(
                UserTenantMembership.user_id == user.id,
                UserTenantMembership.is_active.is_(True),
            )
            .limit(1)
        ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_ROLE", "message": "账号未分配任何角色,请联系管理员"},
        )

    scope = (
        f"provider:{membership.provider_id}"
        if membership.provider_id is not None
        else f"tenant:{membership.tenant_id}"
    )
    tenant_name = db.execute(
        select(Tenant.name).where(Tenant.id == membership.tenant_id)
    ).scalar_one_or_none()

    return IdentityClaims(
        role=membership.role,
        scope=scope,
        tenant_id=membership.tenant_id,
        provider_id=membership.provider_id,
        tenant_name=tenant_name,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec autoluyin-backend pytest tests/test_identity_resolution.py -v`
Expected: PASS(4 passed)

- [ ] **Step 5: 改 `auth.py::login` 用 `resolve_identity`**

把 `poc/backend/app/api/auth.py` 第 50-76 行(从 `tenant_id: int | None = None` 到 `create_access_token(...)` 调用结束)替换为:

```python
    from app.core.identity import resolve_identity

    claims = resolve_identity(db, user)
    user.last_login_at = datetime.now(UTC)

    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": claims.tenant_id,
            "role": claims.role,
            "scope": claims.scope,
            "provider_id": claims.provider_id,
        }
    )
```

并把第 93-101 行 `return TokenResponse(...)` 中的 `tenant_id=tenant_id` 改为 `tenant_id=claims.tenant_id`、`tenant_name=tenant_name` 改为 `tenant_name=claims.tenant_name`、`scope=scope` 改为 `scope=claims.scope`、`role=role` 改为 `role=claims.role`。删除现在已无用的 `membership` 查询块(第 41-48 行)。

- [ ] **Step 6: 改 `auth_extras._issue_token` 用 `resolve_identity`**

把 `poc/backend/app/api/auth_extras.py` 的 `_issue_token`(第 142-197 行)函数体中第 143-165 行(`membership = ...` 到 `tenant_name = db.execute(...)` 块结束)替换为:

```python
    from app.core.identity import resolve_identity

    claims = resolve_identity(db, user)
    user.last_login_at = datetime.now(UTC)
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": claims.tenant_id,
            "role": claims.role,
            "scope": claims.scope,
            "provider_id": claims.provider_id,
        }
    )
```

并把该函数末尾 `return TokenResponse(...)` 中的 `role=role` / `tenant_id=tenant_id` / `tenant_name=tenant_name` / `scope=scope` 改为 `claims.role` / `claims.tenant_id` / `claims.tenant_name` / `claims.scope`。

- [ ] **Step 7: 改 `auth_extras.select_membership` 用 `resolve_identity`**

把 `select_membership`(第 520-596 行)中第 547-555 行(`tenant_id = membership.tenant_id` 到 `).scalar_one_or_none()` 块)替换为:

```python
    from app.core.identity import resolve_identity

    claims = resolve_identity(db, user, membership=membership)
```

并把后续 `create_access_token({...})` 与 `return TokenResponse(...)` 中的 `role` / `scope` / `tenant_id` / `tenant_name` 全部改取 `claims.*`。

- [ ] **Step 8: 改 `ADMIN_LIKE_ROLES`**

`poc/backend/app/api/auth_extras.py` 第 45 行:
```python
ADMIN_LIKE_ROLES = {"admin", "platform_superadmin"}
```
改为(信用代码登录找的是物业 admin,平台超管不再是 membership 角色):
```python
ADMIN_LIKE_ROLES = {"admin"}
```

- [ ] **Step 9: 跑回归 — 登录冒烟**

Run: `docker exec autoluyin-backend pytest tests/test_identity_resolution.py tests/test_role_migration.py -v`
Expected: 全部 PASS

- [ ] **Step 10: Commit**

```bash
git add poc/backend/app/core/identity.py poc/backend/app/api/auth.py poc/backend/app/api/auth_extras.py poc/backend/tests/test_identity_resolution.py
git commit -m "feat: 登录身份解析合并到 identity.py,修 provider scope + 去除默认超管"
```

---

## Task 4:`phone_visibility.py` 改为按 `provider_id` 判定

**Files:**
- Modify: `poc/backend/app/core/phone_visibility.py:27-87`
- Test: `poc/backend/tests/test_phone_visibility.py`(若已存在则改;不存在则建)

> 现状用 `INTERNAL_ROLES` / `PROVIDER_ROLES` 等按角色名分类。新模型下「物业内部 vs 服务商」由 `provider_id` 判定,不再靠角色名。

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/test_phone_visibility.py
from app.core.phone_visibility import should_reveal_owner_phone


def test_internal_org_role_always_reveal():
    # provider_id=None 即物业内部,永远明文
    assert should_reveal_owner_phone(role="admin", provider_id=None) is True
    assert should_reveal_owner_phone(role="agent", provider_id=None) is True


def test_provider_role_reveal_depends_on_contract():
    # provider_id 非空即服务商侧,看合同 + 项目时效
    assert should_reveal_owner_phone(
        role="agent", provider_id=7, contract_active=True, project_active=True
    ) is True
    assert should_reveal_owner_phone(
        role="agent", provider_id=7, contract_active=False
    ) is False


def test_platform_role_never_reveal():
    assert should_reveal_owner_phone(role="superadmin", provider_id=None) is False
    assert should_reveal_owner_phone(role="ops", provider_id=None) is False


def test_legal_role_depends_on_stage():
    assert should_reveal_owner_phone(
        role="legal", provider_id=None, legal_case_stage="litigation_filed"
    ) is True
    assert should_reveal_owner_phone(
        role="legal", provider_id=None, legal_case_stage="closed_won"
    ) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec autoluyin-backend pytest tests/test_phone_visibility.py -v`
Expected: FAIL — `should_reveal_owner_phone()` 缺 `provider_id` 形参 → `TypeError`

- [ ] **Step 3: 重写 `phone_visibility.py` 第 27-87 行**

把第 27-30 行的四个 frozenset 删除,替换为:
```python
from app.core.roles import PLATFORM_ROLES, ROLE_LEGAL
```
(放到文件顶部 import 区,与现有 import 合并。)

把 `should_reveal_owner_phone`(第 64-87 行)整个替换为:
```python
def should_reveal_owner_phone(
    *,
    role: str,
    provider_id: int | None,
    contract_active: bool = False,
    project_active: bool = True,
    legal_case_stage: str | None = None,
) -> bool:
    """根据组织归属 + 角色 + 时效信息决定是否展示明文业主电话。

    Args:
        role: token 中的角色(组织职能角色或平台角色)
        provider_id: 组织归属 —— None=物业内部,非空=服务商
        contract_active: 服务商 ProviderTenantContract 是否有效(仅服务商侧用)
        project_active: 当前项目 plan_end 是否未过(仅服务商侧用,无项目语境默认 True)
        legal_case_stage: 当前法务案件 stage(仅 legal 角色用)
    """
    # 平台角色 —— 永远脱敏
    if role in PLATFORM_ROLES:
        return False
    # 法务 —— 看案件阶段(物业法务 / 服务商法务同规则)
    if role == ROLE_LEGAL:
        return legal_case_stage in LEGAL_ACTIVE_STAGES
    # 服务商侧 —— 看合同 + 项目时效
    if provider_id is not None:
        return contract_active and project_active
    # 物业内部 —— 永远明文
    return True
```

- [ ] **Step 4: 更新 `should_reveal_owner_phone` 的所有调用方**

Run: `docker exec autoluyin-backend grep -rln 'should_reveal_owner_phone' app/`
对每个命中文件:调用处补 `provider_id=` 实参(值取该 endpoint 的 `payload["provider_id"]` 或当前 membership 的 `provider_id`)。逐个文件改完后:

Run: `docker exec autoluyin-backend python -c "import app.main"`
Expected: 无报错(确认无 TypeError / 缺参)

- [ ] **Step 5: 运行测试确认通过**

Run: `docker exec autoluyin-backend pytest tests/test_phone_visibility.py -v`
Expected: PASS(4 passed)

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/core/phone_visibility.py poc/backend/tests/test_phone_visibility.py poc/backend/app/api/
git commit -m "feat: phone_visibility 改为按 provider_id 判定物业/服务商"
```

---

## Task 5:后端 API 层角色字面量全量替换

**Files:**
- Modify: 全部 `poc/backend/app/api/*.py`、`poc/backend/app/schemas/*.py`、`poc/backend/app/workers/`、`poc/backend/app/ws/` 中含旧角色字面量的文件
- Modify: `poc/backend/app/api/admin.py`(4 处 `source_type="INTERNAL"`)、`poc/backend/app/api/provider_admin.py`(1 处 `source_type="PROVIDER"`)

- [ ] **Step 1: 列出所有命中文件**

Run:
```bash
docker exec autoluyin-backend grep -rln -E "'(provider_admin|agent_internal|agent_external|project_manager_property|project_manager_provider|property_manager_property|property_manager_provider|platform_superadmin|platform_super|platform_ops)'" app/
```
记下文件清单。

- [ ] **Step 2: 按映射总表逐文件替换角色字面量**

对每个文件,按本计划顶部「角色映射总表」替换:
- `'provider_admin'` → `'admin'`(若该处是「仅服务商管理员」语义,额外加 `payload["provider_id"] is not None` 判断)
- `'agent_internal'` / `'agent_external'` → `'agent'`(若该处区分内外勤,改用 `work_mode`)
- `'project_manager_property'` / `'project_manager_provider'` / `'property_manager_*'` → `'project_manager'`(物业/服务商之分改用 `provider_id`)
- `'platform_superadmin'` / `'platform_super'` → 改判 `payload["role"] == 'superadmin'`(平台角色现在来自 `platform_role`,登录后仍写进 token 的 `role`)
- `'platform_ops'` → `'ops'`

凡 `require_roles(...)` 的参数同样按上表替换。建议改用 `app.core.roles` 常量(如 `from app.core.roles import ROLE_ADMIN` 再 `require_roles(ROLE_ADMIN)`),消除裸字面量。

> 语义判别提示:替换前读该行上下文 —— 若旧代码靠 `provider_admin` vs `admin` 区分服务商/物业,collapse 后必须用 `provider_id` 补回这个区分,否则会放宽权限。

- [ ] **Step 3: 删 `source_type` 写入点**

`poc/backend/app/api/admin.py` 第 232、270、300、418 行各有一行 `source_type="INTERNAL",` —— 删除这 4 行。
`poc/backend/app/api/provider_admin.py` 第 354 行 `source_type="PROVIDER",` —— 删除这 1 行。

- [ ] **Step 4: 验证无旧字面量残留**

Run:
```bash
docker exec autoluyin-backend grep -rn -E "(provider_admin|agent_internal|agent_external|project_manager_p|property_manager_p|platform_superadmin|platform_super|source_type)" app/
```
Expected: 无输出(0 命中)。若有命中,逐条处理。

- [ ] **Step 5: 验证应用可启动**

Run: `docker exec autoluyin-backend python -c "import app.main; print('import ok')"`
Expected: `import ok`

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/
git commit -m "refactor: 后端 API/schema/worker 角色字面量收敛为新 6 角色 + 删 source_type"
```

---

## Task 6:重写 seed_demo,补服务商催收员 / 督导账号

**Files:**
- Modify: `poc/backend/scripts/seed_demo.py`(`_upsert_membership` 第 96-126 行、第 830-869 行 membership 段)
- Modify: `poc/backend/scripts/seed_demo_extra.py:101`、`poc/backend/scripts/seed_demo_v14.py:419`(`source_type` 写入)
- Modify: `poc/backend/scripts/api_smoke.py`(角色矩阵)

- [ ] **Step 1: `_upsert_membership` 去掉 source_type、加 work_mode**

`poc/backend/scripts/seed_demo.py` 第 96-103 行函数签名改为:
```python
def _upsert_membership(
    db,
    user: UserAccount,
    tenant: Tenant,
    role: str,
    *,
    provider_id: int | None = None,
    work_mode: str | None = None,
) -> None:
```
第 115-122 行构造 `UserTenantMembership(...)` 删除 `source_type="INTERNAL",`,加 `work_mode=work_mode,`。

- [ ] **Step 2: 改第 830-869 行 membership 段为新角色值**

把第 849-869 行整段替换为:
```python
        _upsert_membership(db, admin_user, tenant, "admin")
        _upsert_membership(db, supervisor_user, tenant, "supervisor")
        # v1.6.10 — 督导小李同时拥有催收员身份(多角色切换演示)
        _upsert_membership(db, supervisor_user, tenant, "agent", work_mode="internal")
        _upsert_membership(db, agent_internal_user, tenant, "agent", work_mode="internal")
        _upsert_membership(db, agent_external_user, tenant, "agent", work_mode="external")
        _upsert_membership(db, legal_user, tenant, "legal")
        _upsert_membership(db, workorder_user, tenant, "coordinator")
        _upsert_membership(db, pm_property_user, tenant, "project_manager")

        # 3b. ServiceProvider + Contract
        provider = _upsert_provider(db)
        contract = _upsert_provider_contract(db, tenant, provider)
        _upsert_settlement(db, contract)
        _upsert_membership(
            db, pm_provider_user, tenant, "project_manager", provider_id=provider.id
        )
        _upsert_membership(
            db, provider_admin_user, tenant, "admin", provider_id=provider.id
        )
```

> `ops_user` 的 membership(原第 849 行 `_upsert_membership(db, ops_user, tenant, "platform_ops")`)删除 —— ops 改由 `platform_role` 表达,见 Step 4。

- [ ] **Step 3: 新增服务商催收员 + 服务商督导账号**

在第 844 行 `provider_admin_user, _ = _upsert_user(db, "13000000010", "服务商管理员")` 之后追加:
```python
        provider_agent_user, _ = _upsert_user(db, "13000000011", "服务商催收员小孙")
        provider_supervisor_user, _ = _upsert_user(db, "13000000012", "服务商督导小钱")
```
在 Step 2 的 provider membership 段末尾追加:
```python
        _upsert_membership(
            db, provider_agent_user, tenant, "agent",
            provider_id=provider.id, work_mode="external",
        )
        _upsert_membership(
            db, provider_supervisor_user, tenant, "supervisor", provider_id=provider.id
        )
```

- [ ] **Step 4: 平台账号设 `platform_role`**

`super_user` / `ops_user` 创建后(第 830-831 行附近)追加:
```python
        super_user.platform_role = "superadmin"
        ops_user.platform_role = "ops"
        db.flush()
```

- [ ] **Step 5: 其余 seed 文件删 source_type**

`poc/backend/scripts/seed_demo_extra.py` 第 101 行、`poc/backend/scripts/seed_demo_v14.py` 第 419 行:删除 `source_type=...,` 那一行。若同文件构造的是 agent membership,补 `work_mode=` 实参。

- [ ] **Step 6: 重置 DB 重新 seed**

```bash
cd poc && docker compose down -v && docker compose up -d
```
等 backend healthy(`docker inspect --format '{{.State.Health.Status}}' autoluyin-backend` 显示 `healthy`),然后:
```bash
docker exec autoluyin-backend python -m scripts.seed_demo
```
Expected: 全部 `[created]` 行,无 traceback

- [ ] **Step 7: 更新 `api_smoke.py` 角色矩阵**

把 `scripts/api_smoke.py` 中的角色↔手机号↔端点矩阵按新模型更新:平台超管/运营员仍是 13000000000/13000000001;13000000005 现在是 `agent`;新增 13000000011(服务商催收员)、13000000012(服务商督导)。端点路径不变。

Run: `docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke`
Expected: 全角色 ✅,退出码 0

- [ ] **Step 8: Commit**

```bash
git add poc/backend/scripts/
git commit -m "feat: seed 改用新角色模型 + 补服务商催收员/督导账号"
```

---

## Task 7:后端测试套件适配

**Files:**
- Modify: `poc/backend/tests/conftest.py` 及 `tests/` 下所有引用旧角色字面量的测试

- [ ] **Step 1: 列出受影响测试**

Run:
```bash
docker exec autoluyin-backend grep -rln -E "(provider_admin|agent_internal|agent_external|project_manager_p|property_manager_p|platform_superadmin|platform_super|platform_ops|source_type)" tests/
```

- [ ] **Step 2: 按映射总表替换**

每个命中文件按「角色映射总表」替换字面量;`source_type=` 入参删除;构造 agent membership 处补 `work_mode=`;构造平台用户处改设 `platform_role`。

- [ ] **Step 3: 跑全量后端测试**

Run: `docker exec autoluyin-backend pytest -q`
Expected: 全绿。失败项逐个修(多为 fixture 残留旧角色名)。

- [ ] **Step 4: 覆盖率检查**

Run: `docker exec autoluyin-backend pytest --cov=app --cov-report=term-missing -q`
Expected: P0 模块行覆盖率 ≥ 80%,`auth` / `identity` / `phone_visibility` ≥ 90%

- [ ] **Step 5: Commit**

```bash
git add poc/backend/tests/
git commit -m "test: 后端测试套件适配新角色模型"
```

---

## Task 8:PC 前端角色字面量收敛

**Files:**
- Modify: `frontend/src/types/index.ts`(`UserRole`)
- Modify: `frontend/src/` 下全部引用旧角色字面量的文件(`RoleHomeRedirect`、`nav.ts`、路由守卫、各页面)

- [ ] **Step 1: 列出前端命中文件**

Run:
```bash
grep -rln -E "(provider_admin|agent_internal|agent_external|project_manager_property|project_manager_provider|platform_superadmin|platform_ops)" frontend/src/
```

- [ ] **Step 2: 改 `UserRole` 类型**

打开 `frontend/src/types/index.ts`,把 `UserRole` 联合类型改为新值域:
```typescript
export type OrgRole =
  | "admin"
  | "project_manager"
  | "supervisor"
  | "agent"
  | "legal"
  | "coordinator";
export type PlatformRole = "superadmin" | "ops";
export type UserRole = OrgRole | PlatformRole;
export type WorkMode = "internal" | "external";
```
(若 `UserRole` 当前为别的形态,保留其导出名,只换成员值。)

- [ ] **Step 3: 逐文件替换字面量**

按「角色映射总表」替换。重点:
- `RoleHomeRedirect` —— 旧 `project_manager_property` / `project_manager_provider` 现在都是 `project_manager`,落地页若需区分物业/服务商,改判登录响应里的 `scope`(`provider:` 前缀 = 服务商侧)。
- `nav.ts` 菜单 —— 按角色显隐的项,服务商专属菜单改判 `scope` 而非角色名。
- `agent_internal`/`agent_external` 区分 → 改用后端返回的 `work_mode`(`IdentityClaims`/`TokenResponse` 不含 work_mode → 前端从 `/api/v1/me` 或 `/agent/me` 接口取)。

> 依赖说明:若前端需要 `work_mode`,确认 `/api/v1/me` 或 `/agent/me` 响应是否已含该字段;未含则在 Task 5 范围内给对应 schema 补 `work_mode`。

- [ ] **Step 4: 类型检查 + 构建**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: 0 error(注意:`E2E_SMOKE.md` 记录有 ~29 个 pre-existing TS 错误;本步骤只需保证「不新增」错误,不负责修历史错误)

- [ ] **Step 5: 验证无残留**

Run: `grep -rn -E "(provider_admin|agent_internal|agent_external|project_manager_property|project_manager_provider|platform_superadmin|platform_ops)" frontend/src/`
Expected: 0 命中

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "refactor: PC 前端角色字面量收敛为新模型"
```

---

## Task 9:Android 角色字面量收敛

**Files:**
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt`
- Modify: `poc/android/app/src/test/` 下引用旧角色的测试

- [ ] **Step 1: 列出 Android 命中**

Run: `grep -rn -E '(agent_internal|agent_external|provider_admin|project_manager_p|platform_super)' $(find poc/android -name '*.kt')`

- [ ] **Step 2: 替换**

`Api.kt` 的 `agent_internal` → `agent`(Android 外勤 App 实际用 `agent` + `work_mode=external`;若该处是默认值/占位,改为 `agent`)。`AudioStreamClient.kt` 的 `supervisor` 是 WS 路径常量、角色名未变,无需改 —— 仅确认。其余按映射总表替换。

- [ ] **Step 3: 编译 + 单测**

Run: `cd poc/android && ./gradlew testDebugUnitTest`
Expected: BUILD SUCCESSFUL

- [ ] **Step 4: Commit**

```bash
git add poc/android/
git commit -m "refactor: Android 角色字面量收敛为新模型"
```

---

## Task 10:文档同步

**Files:**
- Modify: `docs/account-architecture.md`、`docs/E2E_SMOKE.md`、`CLAUDE.md`

- [ ] **Step 1: 改 `docs/E2E_SMOKE.md` 角色矩阵**

把测试矩阵表(第 24-37 行、第 54-71 行)更新为新角色模型:`role` 列改新值;新增 13000000011(服务商催收员 `agent`+provider)、13000000012(服务商督导 `supervisor`+provider);平台超管/运营员标注「`platform_role`,无 membership」。

- [ ] **Step 2: 改 `docs/account-architecture.md`**

在文档开头加一节「v2.2 角色模型重构」,说明四维模型(`platform_role` / `role` / `provider_id` / `work_mode`)与旧 11 角色的映射,并标注本文档其余部分的 v1.4/v1.5 旧角色名已被取代。

- [ ] **Step 3: 改 `CLAUDE.md` 多租户规则节**

「多租户关键规则」节补一句:组织归属由 `UserTenantMembership.provider_id` 表达(`NULL`=物业 / 非空=服务商);角色常量统一在 `app/core/roles.py`。

- [ ] **Step 4: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: 同步角色模型重构 — account-architecture/E2E_SMOKE/CLAUDE"
```

---

## Task 11:端到端冒烟验收

**Files:** 无(纯验证)

- [ ] **Step 1: 全量后端测试**

Run: `docker exec autoluyin-backend pytest -q`
Expected: 全绿

- [ ] **Step 2: API 冒烟(全角色)**

Run: `docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke`
Expected: 全角色 ✅,退出码 0

- [ ] **Step 3: 四个关键账号登录 + scope 验证**

Run:
```bash
for acct in 13000000008 13000000010 13000000011 13000000012; do
  curl -s -X POST http://localhost:18000/api/v1/auth/login-universal \
    -H 'Content-Type: application/json' \
    -d "{\"account\":\"$acct\",\"password\":\"Demo@123!\"}" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('$acct', d.get('role'), d.get('scope'))"
done
```
Expected:
- `13000000008 project_manager tenant:{id}`
- `13000000010 admin provider:{id}`
- `13000000011 agent provider:{id}`
- `13000000012 supervisor provider:{id}`
(服务商账号 scope 前缀必须是 `provider:`)

- [ ] **Step 4: 平台超管登录验证**

Run:
```bash
curl -s -X POST http://localhost:18000/api/v1/auth/login-universal \
  -H 'Content-Type: application/json' \
  -d '{"account":"13000000000","password":"Demo@123!"}' \
| python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('role'), d.get('scope'))"
```
Expected: `superadmin platform`

- [ ] **Step 5: 前端构建 + 视觉抽查**

Run: `cd frontend && npm run build`
Expected: 构建成功。浏览器开 `http://localhost:5173`,用 13000000010 / 13000000011 登录,确认落地页与菜单正常。

- [ ] **Step 6: 最终提交(收尾)**

```bash
git add -A
git commit -m "chore: 角色模型重构端到端冒烟通过" --allow-empty
```

---

## 验收标准(对应 spec §2)

- [ ] `UserTenantMembership.role` 仅含 6 个组织职能角色;DB CHECK 拒绝其他值
- [ ] `UserAccount.platform_role` 承载 superadmin/ops;无 membership 不再默认超管
- [ ] 服务商账号登录 `scope` 前缀为 `provider:{id}`
- [ ] `source_type` 列已删除
- [ ] seed 含服务商催收员(13000000011)、服务商督导(13000000012)真账号
- [ ] 三端无旧角色字面量残留(grep 0 命中)
- [ ] `api_smoke.py` 全角色通过;后端覆盖率守住 P0 ≥ 80% / 关键路径 ≥ 90%
- [ ] 后端无新增字面量 —— 角色一律引用 `app/core/roles.py`
