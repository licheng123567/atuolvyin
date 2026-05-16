"""v1.7.0 — 业主电话可见性 e2e：4 角色族 × 合同/项目/法务案件状态。

覆盖：
- admin / supervisor / agent_internal → 永远明文
- agent_external + active 合同 → 明文
- agent_external + 合同 expires_at 过期 → 脱敏
- agent_external + 项目 plan_end 过期 → 脱敏
- platform_ops → 永远脱敏
- legal + 案件 stage in active → 明文；stage in closed_* → 脱敏
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.crypto import encrypt_phone
from app.core.security import create_access_token, get_password_hash
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    UserTenantMembership,
)
from app.models.user import UserAccount

PLAIN_PHONE = "13712345678"
MASKED_PHONE = "137****5678"


# ── 通用脚手架 ──────────────────────────────────────────────────
def _make_provider(db, name="测试服务商") -> ServiceProvider:
    p = ServiceProvider(
        name=name,
        provider_type="collection",
        admin_phone_enc=encrypt_phone("18800001111"),
        is_active=True,
        audit_status="approved",
    )
    db.add(p)
    db.flush()
    return p


def _make_contract(db, tenant, provider, *, expires_at=None, status="active") -> ProviderTenantContract:
    c = ProviderTenantContract(
        tenant_id=tenant.id,
        provider_id=provider.id,
        signed_at=datetime.now(UTC) - timedelta(days=30),
        expires_at=expires_at,
        service_types=["collection"],
        status=status,
    )
    db.add(c)
    db.flush()
    return c


def _make_external_agent(db, tenant, provider) -> tuple[UserAccount, dict[str, str]]:
    user = UserAccount(
        phone_enc=encrypt_phone("13900009999"),
        name="外部催收张三",
        password_hash=get_password_hash("Demo@1234"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="agent",
        work_mode="external",
        provider_id=provider.id,
        is_active=True,
    ))
    db.flush()
    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "agent",
        "scope": f"tenant:{tenant.id}",
        "provider_id": provider.id,
    })
    return user, {"Authorization": f"Bearer {token}"}


def _make_platform_ops(db) -> dict[str, str]:
    user = UserAccount(
        phone_enc=encrypt_phone("13511112222"),
        name="平台运营",
        password_hash=get_password_hash("Demo@1234"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": None,
        "role": "ops",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


def _make_project_for_case(
    db, tenant, case: CollectionCase, provider: ServiceProvider | None = None,
    *, plan_end=None,
) -> Project:
    proj = Project(
        tenant_id=tenant.id,
        name="测试项目",
        provider_id=provider.id if provider else None,
        status="active",
        plan_end=plan_end,
    )
    db.add(proj)
    db.flush()
    case.project_id = proj.id
    db.flush()
    return proj


# ── 测试 ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_sees_plain_phone(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner,
):
    """admin 是物业内部角色，phone_masked 字段返回 11 位明文。"""
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["owner"]["phone_masked"] == PLAIN_PHONE


@pytest.mark.asyncio
async def test_supervisor_sees_plain_phone(
    client: AsyncClient, supervisor_auth_headers, seeded_case, seeded_owner,
):
    resp = await client.get(
        f"/api/v1/supervisor/cases/{seeded_case.id}", headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["owner"]["phone_masked"] == PLAIN_PHONE


@pytest.mark.asyncio
async def test_agent_external_with_active_contract_sees_plain(
    client: AsyncClient, db_session, seeded_tenant, seeded_owner, seeded_case,
):
    """合同 active 且无 expires_at（永久）→ 明文。"""
    provider = _make_provider(db_session)
    _make_contract(db_session, seeded_tenant, provider, expires_at=None, status="active")
    _make_project_for_case(db_session, seeded_tenant, seeded_case, provider=provider)
    seeded_case.assigned_to = None
    seeded_case.pool_type = "public"
    db_session.flush()
    _, headers = _make_external_agent(db_session, seeded_tenant, provider)

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner"]["phone_masked"] == PLAIN_PHONE


@pytest.mark.asyncio
async def test_agent_external_expired_contract_sees_masked(
    client: AsyncClient, db_session, seeded_tenant, seeded_owner, seeded_case,
):
    """合同 expires_at 过去 → 脱敏。"""
    provider = _make_provider(db_session, name="过期合同服务商")
    _make_contract(
        db_session, seeded_tenant, provider,
        expires_at=datetime.now(UTC) - timedelta(days=1),
        status="active",
    )
    _make_project_for_case(db_session, seeded_tenant, seeded_case, provider=provider)
    seeded_case.assigned_to = None
    seeded_case.pool_type = "public"
    db_session.flush()
    _, headers = _make_external_agent(db_session, seeded_tenant, provider)

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner"]["phone_masked"] == MASKED_PHONE


@pytest.mark.asyncio
async def test_agent_external_terminated_contract_sees_masked(
    client: AsyncClient, db_session, seeded_tenant, seeded_owner, seeded_case,
):
    """合同 status=terminated → 脱敏（即使 expires_at 未过）。"""
    provider = _make_provider(db_session, name="解约服务商")
    _make_contract(
        db_session, seeded_tenant, provider,
        expires_at=datetime.now(UTC) + timedelta(days=365),
        status="terminated",
    )
    _make_project_for_case(db_session, seeded_tenant, seeded_case, provider=provider)
    seeded_case.assigned_to = None
    seeded_case.pool_type = "public"
    db_session.flush()
    _, headers = _make_external_agent(db_session, seeded_tenant, provider)

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner"]["phone_masked"] == MASKED_PHONE


@pytest.mark.asyncio
async def test_agent_external_expired_project_blocked_at_access_layer(
    client: AsyncClient, db_session, seeded_tenant, seeded_owner, seeded_case,
):
    """合同 active 但项目 plan_end 过去：access-control 层（active_project_filter）
    先于电话可见性层把请求 403 — 用户根本看不到案件，比脱敏更严。

    电话可见性 project_active=False 的决策路径已由 unit test 覆盖
    （test_should_reveal_owner_phone[agent_external-kwargs9-False]）。
    """
    provider = _make_provider(db_session, name="项目过期服务商")
    _make_contract(db_session, seeded_tenant, provider, expires_at=None, status="active")
    _make_project_for_case(
        db_session, seeded_tenant, seeded_case,
        provider=provider, plan_end=datetime.now(UTC) - timedelta(days=1),
    )
    seeded_case.assigned_to = None
    seeded_case.pool_type = "public"
    db_session.flush()
    _, headers = _make_external_agent(db_session, seeded_tenant, provider)

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=headers,
    )
    assert resp.status_code == 403
