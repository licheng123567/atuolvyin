"""Task 3 — identity 解析单元测试(TDD 先失败后实现)。

测试 resolve_identity() 的四个核心行为:
1. platform_role 优先于 membership
2. provider membership → scope = 'provider:{id}'
3. tenant membership → scope = 'tenant:{id}'
4. 无 platform_role 且无 membership → 403
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.identity import resolve_identity
from app.core.crypto import encrypt_phone
from app.models.tenant import ServiceProvider, Tenant, UserTenantMembership
from app.models.user import UserAccount


# ─── Inline factories ────────────────────────────────────────────────────────

_counter = 0


@pytest.fixture
def make_user(db_session):
    """Factory: inserts and returns a UserAccount.

    make_user()                 → no platform_role
    make_user(platform_role="superadmin")
    """

    def _factory(**kwargs):
        global _counter
        _counter += 1
        # Use uuid so phone_enc is always unique across test sessions
        unique = str(uuid.uuid4()).replace("-", "")[:16]
        user = UserAccount(
            phone_enc=encrypt_phone(f"139{unique[:8]}"),
            name=kwargs.pop("name", "测试用户"),
            password_hash=kwargs.pop("password_hash", "hashed_pw"),
            is_active=kwargs.pop("is_active", True),
            **kwargs,
        )
        db_session.add(user)
        db_session.flush()
        return user

    return _factory


@pytest.fixture
def make_membership(db_session):
    """Factory: inserts and returns a UserTenantMembership.

    Parameters
    ----------
    user       : UserAccount (required)
    role       : str (required) — must be a valid org role
    provider_id: int | None    — if given, ensures ServiceProvider row exists
    work_mode  : str | None    — required when role='agent'
    """

    def _factory(user: UserAccount, *, role: str, provider_id: int | None = None, work_mode: str | None = None):
        # Ensure a Tenant row exists (reuse or create)
        from sqlalchemy import select

        tenant = db_session.execute(select(Tenant).limit(1)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                name="Factory Tenant",
                admin_phone_enc=encrypt_phone("13900139099"),
                plan="trial",
                is_active=True,
            )
            db_session.add(tenant)
            db_session.flush()

        # Ensure ServiceProvider row exists when provider_id is given
        if provider_id is not None:
            from sqlalchemy import select as sa_select

            sp = db_session.get(ServiceProvider, provider_id)
            if sp is None:
                sp = ServiceProvider(
                    id=provider_id,
                    name="Factory Provider",
                    provider_type="collection",
                    admin_phone_enc=encrypt_phone("13800000001"),
                    is_active=True,
                )
                db_session.add(sp)
                db_session.flush()

        membership = UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role=role,
            provider_id=provider_id,
            work_mode=work_mode,
            is_active=True,
        )
        db_session.add(membership)
        db_session.flush()
        return membership

    return _factory


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_platform_role_takes_precedence(db_session, make_user):
    """platform_role 设置时直接返回平台身份,忽略任何 membership。"""
    user = make_user(platform_role="superadmin")
    claims = resolve_identity(db_session, user)
    assert claims.role == "superadmin"
    assert claims.scope == "platform"
    assert claims.tenant_id is None


def test_provider_membership_scope_is_provider(db_session, make_user, make_membership):
    """provider_id 非空的 membership → scope 应为 'provider:{id}'。"""
    user = make_user()
    make_membership(user, role="admin", provider_id=1)
    claims = resolve_identity(db_session, user)
    assert claims.scope == "provider:1"


def test_tenant_membership_scope_is_tenant(db_session, make_user, make_membership):
    """普通 tenant membership(provider_id=None) → scope 应为 'tenant:{tenant_id}'。"""
    user = make_user()
    m = make_membership(user, role="supervisor", provider_id=None)
    claims = resolve_identity(db_session, user)
    assert claims.scope == f"tenant:{m.tenant_id}"


def test_no_role_no_membership_rejected(db_session, make_user):
    """无 platform_role 且无 membership → 不再默认超管,拒绝 403。"""
    user = make_user(platform_role=None)
    with pytest.raises(HTTPException) as exc:
        resolve_identity(db_session, user)
    assert exc.value.status_code == 403
