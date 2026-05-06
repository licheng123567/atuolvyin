"""Sprint 13 — Project Manager dashboard tests."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def property_pm_auth_headers(db_session, seeded_user, seeded_tenant):
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="project_manager_property",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "project_manager_property",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def provider_pm_auth_headers(db_session, seeded_tenant):
    """Create a provider PM with an active provider membership."""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import (
        ProviderTenantContract,
        ServiceProvider,
        UserTenantMembership,
    )
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13511135111"),
        name="服务商PM",
        password_hash=get_password_hash("Pm@12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    provider = ServiceProvider(
        name="测试催收服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13522135222"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()

    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="project_manager_provider",
        source_type="EXTERNAL",
        provider_id=provider.id,
        is_active=True,
    )
    db_session.add(membership)

    contract = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=provider.id,
        signed_at=datetime.now(UTC),
        service_types=["collection"],
        status="active",
    )
    db_session.add(contract)
    db_session.flush()

    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": seeded_tenant.id,
        "role": "project_manager_provider",
        "scope": f"provider:{provider.id}",
    })
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": user,
        "provider": provider,
        "contract": contract,
    }


# ── Property PM dashboard ───────────────────────────────────


@pytest.mark.asyncio
async def test_property_pm_dashboard_returns_stats(
    client: AsyncClient,
    property_pm_auth_headers,
    seeded_case,
    db_session,
    seeded_tenant,
):
    # Add a workorder + a non-closed legal case so counts are > 0
    from app.models.work import LegalCase, WorkOrder

    db_session.add(
        WorkOrder(
            tenant_id=seeded_tenant.id,
            order_type="quality",
            description="待处理工单",
            status="open",
        )
    )
    db_session.add(
        LegalCase(
            tenant_id=seeded_tenant.id,
            case_id=seeded_case.id,
            stage="evidence_collection",
            amount_disputed=Decimal("1000.00"),
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/pm/dashboard/property", headers=property_pm_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "active_cases_count" in data
    assert data["active_cases_count"] >= 1
    assert data["pending_workorders"] >= 1
    assert data["escalated_legal_cases"] >= 1
    assert isinstance(data["top_overdue"], list)


@pytest.mark.asyncio
async def test_property_pm_dashboard_rejects_provider_role(
    client: AsyncClient, provider_pm_auth_headers
):
    resp = await client.get(
        "/api/v1/pm/dashboard/property",
        headers=provider_pm_auth_headers["headers"],
    )
    assert resp.status_code == 403


# ── Provider PM dashboard ────────────────────────────────────


@pytest.mark.asyncio
async def test_provider_pm_dashboard_returns_stats(
    client: AsyncClient, provider_pm_auth_headers
):
    resp = await client.get(
        "/api/v1/pm/dashboard/provider",
        headers=provider_pm_auth_headers["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_contracts_count"] >= 1
    assert "top_tenants_by_volume" in data
    assert isinstance(data["top_tenants_by_volume"], list)


@pytest.mark.asyncio
async def test_provider_pm_dashboard_rejects_property_role(
    client: AsyncClient, property_pm_auth_headers
):
    resp = await client.get(
        "/api/v1/pm/dashboard/provider", headers=property_pm_auth_headers
    )
    assert resp.status_code == 403
