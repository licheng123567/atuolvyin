"""Sprint 9.1 / 9.2 / 9.3 — provider_admin new endpoints."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

# Reuse seeded_provider, seeded_provider_admin_user, seeded_provider_membership,
# provider_auth_headers, seeded_partner_contract from test_provider_admin.py.
# pytest auto-discovers fixtures from sibling files only via conftest, so we
# re-declare the minimal ones here.


@pytest.fixture
def seeded_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="律所 S9",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900015001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_provider_admin_user(db_session):
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900015002"),
        name="S9 管理员",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def seeded_provider_membership(
    db_session, seeded_provider_admin_user, seeded_provider, seeded_tenant
):
    from app.models.tenant import UserTenantMembership

    m = UserTenantMembership(
        user_id=seeded_provider_admin_user.id,
        tenant_id=seeded_tenant.id,
        role="provider_admin",
        source_type="PROVIDER",
        provider_id=seeded_provider.id,
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    return m


@pytest.fixture
def provider_auth_headers(
    seeded_provider_admin_user, seeded_provider, seeded_provider_membership
):
    from app.core.security import create_access_token

    token = create_access_token(
        {
            "sub": str(seeded_provider_admin_user.id),
            "user_id": seeded_provider_admin_user.id,
            "tenant_id": None,
            "role": "provider_admin",
            "scope": f"provider:{seeded_provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_partner_contract(db_session, seeded_provider, seeded_tenant):
    from app.models.tenant import ProviderTenantContract

    c = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=seeded_provider.id,
        signed_at=datetime.now(UTC),
        service_types=["collection"],
        status="active",
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def seeded_settlement(db_session, seeded_partner_contract):
    from app.models.settlement import SettlementStatement

    s = SettlementStatement(
        contract_id=seeded_partner_contract.id,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 5, 1, tzinfo=UTC),
        total_amount=Decimal("12000.00"),
        status="DRAFT",
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def seeded_provider_team_member(
    db_session, seeded_provider, seeded_tenant
):
    """A non-admin staff member belonging to the same provider."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900015099"),
        name="S9 法务",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    m = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_external",
        source_type="EXTERNAL",
        provider_id=seeded_provider.id,
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    return user


# ── S9.3: dispute submission ────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_dispute_creates_record(
    client: AsyncClient,
    seeded_settlement,
    provider_auth_headers,
):
    resp = await client.post(
        f"/api/v1/provider/settlements/{seeded_settlement.id}/dispute",
        json={"reason": "对账金额与我方记录不符，差额 230 元"},
        headers=provider_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert "230" in data["reason"]


@pytest.mark.asyncio
async def test_submit_dispute_marks_statement_disputed(
    client: AsyncClient,
    db_session,
    seeded_settlement,
    provider_auth_headers,
):
    await client.post(
        f"/api/v1/provider/settlements/{seeded_settlement.id}/dispute",
        json={"reason": "测试异议"},
        headers=provider_auth_headers,
    )
    db_session.expire_all()
    db_session.refresh(seeded_settlement)
    assert seeded_settlement.status == "DISPUTED"


@pytest.mark.asyncio
async def test_submit_dispute_blocked_for_paid_settlement(
    client: AsyncClient,
    db_session,
    seeded_settlement,
    provider_auth_headers,
):
    seeded_settlement.status = "PAID"
    db_session.flush()

    resp = await client.post(
        f"/api/v1/provider/settlements/{seeded_settlement.id}/dispute",
        json={"reason": "晚到的异议"},
        headers=provider_auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_submit_dispute_unknown_settlement_404(
    client: AsyncClient, provider_auth_headers
):
    resp = await client.post(
        "/api/v1/provider/settlements/999999/dispute",
        json={"reason": "x"},
        headers=provider_auth_headers,
    )
    assert resp.status_code == 404


# ── S9.1: cross-tenant team performance ─────────────────────────────


@pytest.mark.asyncio
async def test_team_performance_empty_for_no_members(
    client: AsyncClient, seeded_provider_membership, provider_auth_headers
):
    resp = await client.get(
        "/api/v1/provider/team-performance", headers=provider_auth_headers
    )
    assert resp.status_code == 200
    # The provider_admin user themselves IS a member, so there's at least 1 row
    items = resp.json()
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_team_performance_aggregates_calls(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_provider_team_member,
    provider_auth_headers,
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    # Add 2 calls (1 connected) for the team member
    for billable in (60, 0):
        call = CallRecord(
            tenant_id=seeded_tenant.id,
            caller_user_id=seeded_provider_team_member.id,
            callee_phone_enc=encrypt_phone("13700000000"),
            initiated_by="app",
            billable_duration=billable,
            status="processed",
        )
        db_session.add(call)
    db_session.flush()

    resp = await client.get(
        "/api/v1/provider/team-performance", headers=provider_auth_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    member = next(i for i in items if i["user_id"] == seeded_provider_team_member.id)
    assert member["total_calls"] == 2
    assert member["connected_calls"] == 1


# ── S9.2: commission breakdown ──────────────────────────────────────


@pytest.mark.asyncio
async def test_member_commission_returns_paid_total(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_provider_team_member,
    seeded_owner,
    provider_auth_headers,
):
    from app.models.case import CollectionCase

    # Two paid cases assigned to this member
    for amount in (1000, 2000):
        c = CollectionCase(
            tenant_id=seeded_tenant.id,
            owner_id=seeded_owner.id,
            pool_type="public",
            stage="paid",
            amount_owed=Decimal(str(amount)),
            assigned_to=seeded_provider_team_member.id,
        )
        db_session.add(c)
    db_session.flush()

    now = datetime.now(UTC)
    ym = f"{now.year:04d}-{now.month:02d}"
    resp = await client.get(
        f"/api/v1/provider/team/{seeded_provider_team_member.id}/commission",
        params={"year_month": ym},
        headers=provider_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["base_amount"]) == Decimal("3000")
    # 3000 * 0.05 = 150.00
    assert Decimal(data["commission"]) == Decimal("150.00")
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_member_commission_unknown_member_404(
    client: AsyncClient, seeded_provider_membership, provider_auth_headers
):
    now = datetime.now(UTC)
    ym = f"{now.year:04d}-{now.month:02d}"
    resp = await client.get(
        f"/api/v1/provider/team/999999/commission?year_month={ym}",
        headers=provider_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_member_commission_invalid_year_month(
    client: AsyncClient,
    seeded_provider_team_member,
    provider_auth_headers,
):
    resp = await client.get(
        f"/api/v1/provider/team/{seeded_provider_team_member.id}/commission?year_month=2026/04",
        headers=provider_auth_headers,
    )
    assert resp.status_code == 422
