"""Sprint 14 — provider_admin (服务商工作台) API tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone

# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_provider(db_session):
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="测试律所14",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900014001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_provider_admin_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900014002"),
        name="服务商管理员王经理",
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
    """The provider_admin user's membership row — provider_id is the link."""
    from app.models.tenant import UserTenantMembership

    m = UserTenantMembership(
        user_id=seeded_provider_admin_user.id,
        tenant_id=seeded_tenant.id,  # required NOT NULL — uses seed tenant
        role="admin",
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
            "role": "admin",
            "provider_id": seeded_provider.id,
            "scope": f"provider:{seeded_provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_partner_contract(db_session, seeded_provider, seeded_tenant):
    """The provider's contract with seeded_tenant."""
    from app.models.tenant import ProviderTenantContract

    c = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=seeded_provider.id,
        signed_at=datetime.now(UTC) - timedelta(days=10),
        expires_at=datetime.now(UTC) + timedelta(days=355),
        service_types=["legal", "collection"],
        status="active",
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def seeded_provider_settlements(
    db_session, seeded_partner_contract
):
    """Three statements: PAID this month, CONFIRMED, DRAFT."""
    from app.models.settlement import SettlementStatement

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    paid = SettlementStatement(
        contract_id=seeded_partner_contract.id,
        period_start=month_start,
        period_end=month_start + timedelta(days=27),
        total_amount=Decimal("5000.00"),
        status="PAID",
        paid_at=month_start + timedelta(days=15),
    )
    confirmed = SettlementStatement(
        contract_id=seeded_partner_contract.id,
        period_start=datetime(2026, 3, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 31, tzinfo=UTC),
        total_amount=Decimal("3000.00"),
        status="CONFIRMED",
    )
    draft = SettlementStatement(
        contract_id=seeded_partner_contract.id,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 4, 30, tzinfo=UTC),
        total_amount=Decimal("1000.00"),
        status="DRAFT",
    )
    db_session.add_all([paid, confirmed, draft])
    db_session.flush()
    return {"paid": paid, "confirmed": confirmed, "draft": draft}


@pytest.fixture
def seeded_provider_team(
    db_session, seeded_provider, seeded_tenant
):
    """A teammate user under the same provider."""
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    teammate = UserAccount(
        phone_enc=encrypt_phone("13900014003"),
        name="服务商职员李四",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(teammate)
    db_session.flush()
    m = UserTenantMembership(
        user_id=teammate.id,
        tenant_id=seeded_tenant.id,
        role="legal",
        provider_id=seeded_provider.id,
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    return teammate


# ─── tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_returns_provider_kpi(
    client,
    provider_auth_headers,
    seeded_provider,
    seeded_partner_contract,
    seeded_provider_settlements,
    seeded_provider_team,
):
    resp = await client.get(
        "/api/v1/provider/dashboard/stats", headers=provider_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_name"] == "测试律所14"
    assert body["partner_tenant_count"] == 1
    # team_count includes the provider_admin (1) + teammate (1) memberships
    assert body["team_count"] >= 2
    # revenue_month = sum of PAID this month = 5000.00
    assert Decimal(str(body["revenue_month"])) == Decimal("5000.00")
    # pending = DRAFT 1000 + CONFIRMED 3000 = 4000
    assert Decimal(str(body["pending_settlement_total"])) == Decimal("4000.00")
    # contracts list
    assert isinstance(body["contracts"], list)
    assert any(c["tenant_id"] == seeded_partner_contract.tenant_id for c in body["contracts"])


@pytest.mark.asyncio
async def test_dashboard_403_when_property_side_token(
    client, db_session, seeded_user, seeded_tenant
):
    """v2.2 角色重构：require_provider_roles 先于业务逻辑检查 provider_id；
    没有 provider_id 的 token（物业侧）访问 /provider/ 端点直接 403 ERR_FORBIDDEN，
    而不是之前的 404 ERR_NO_PROVIDER（业务层）。"""
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    m = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="admin",
        provider_id=None,
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()

    # Token has no provider_id → require_provider_roles sees property-side → 403
    token = create_access_token(
        {
            "sub": str(seeded_user.id),
            "user_id": seeded_user.id,
            "tenant_id": seeded_tenant.id,
            "role": "admin",
            "scope": f"tenant:{seeded_tenant.id}",
        }
    )
    resp = await client.get(
        "/api/v1/provider/dashboard/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_partner_tenants_list_basic(
    client,
    provider_auth_headers,
    seeded_partner_contract,
    seeded_tenant,
):
    resp = await client.get(
        "/api/v1/provider/tenants", headers=provider_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["tenant_id"] == seeded_tenant.id
    assert item["name"] == seeded_tenant.name
    assert item["contract_id"] == seeded_partner_contract.id
    assert "legal" in item["service_types"]
    assert item["status"] == "active"


@pytest.mark.asyncio
async def test_team_list_filtered_by_provider(
    client,
    provider_auth_headers,
    seeded_provider_admin_user,
    seeded_provider_team,
    db_session,
    seeded_tenant,
):
    """Only members under this provider are returned, regardless of tenant."""
    # Add a noise user with NO provider link — must not appear
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    noise = UserAccount(
        phone_enc=encrypt_phone("13900014999"),
        name="无关员工",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(noise)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=noise.id,
            tenant_id=seeded_tenant.id,
            role="agent",
            work_mode="internal",
            provider_id=None,
            is_active=True,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/provider/team", headers=provider_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {m["user_id"] for m in body["items"]}
    assert seeded_provider_admin_user.id in ids
    assert seeded_provider_team.id in ids
    assert noise.id not in ids
    # phone_masked must never expose plain digits
    sample = next(m for m in body["items"] if m["user_id"] == seeded_provider_team.id)
    assert "****" in sample["phone_masked"]


@pytest.mark.asyncio
async def test_team_toggle_active(
    client,
    provider_auth_headers,
    seeded_provider_team,
):
    resp = await client.patch(
        f"/api/v1/provider/team/{seeded_provider_team.id}/active",
        headers=provider_auth_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == seeded_provider_team.id
    assert body["is_active"] is False

    # Re-enable
    resp2 = await client.patch(
        f"/api/v1/provider/team/{seeded_provider_team.id}/active",
        headers=provider_auth_headers,
        json={"is_active": True},
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_team_cannot_deactivate_self(
    client,
    provider_auth_headers,
    seeded_provider_admin_user,
):
    resp = await client.patch(
        f"/api/v1/provider/team/{seeded_provider_admin_user.id}/active",
        headers=provider_auth_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_CANNOT_DEACTIVATE_SELF"


@pytest.mark.asyncio
async def test_settlements_list_filtered_by_provider(
    client,
    provider_auth_headers,
    seeded_provider_settlements,
):
    resp = await client.get(
        "/api/v1/provider/settlements", headers=provider_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    statuses = {it["status"] for it in body["items"]}
    assert statuses == {"PAID", "CONFIRMED", "DRAFT"}
    # tenant_name populated
    sample = body["items"][0]
    assert sample["tenant_name"]
    # filter by status
    resp2 = await client.get(
        "/api/v1/provider/settlements?status=PAID",
        headers=provider_auth_headers,
    )
    assert resp2.status_code == 200
    items2 = resp2.json()["items"]
    assert all(i["status"] == "PAID" for i in items2)
    assert len(items2) == 1


@pytest.mark.asyncio
async def test_settlements_detail_includes_disputes(
    client,
    db_session,
    provider_auth_headers,
    seeded_provider_settlements,
    seeded_provider_admin_user,
):
    from app.models.settlement import DisputeRecord

    draft = seeded_provider_settlements["draft"]
    rec = DisputeRecord(
        statement_id=draft.id,
        reason="金额对不上",
        status="open",
        submitted_by=seeded_provider_admin_user.id,
    )
    db_session.add(rec)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/provider/settlements/{draft.id}",
        headers=provider_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == draft.id
    assert body["tenant_name"]
    assert isinstance(body["disputes"], list)
    assert len(body["disputes"]) == 1
    assert body["disputes"][0]["reason"] == "金额对不上"


@pytest.mark.asyncio
async def test_non_provider_admin_forbidden(
    client, admin_auth_headers, agent_auth_headers
):
    """Non provider_admin roles must get 403 on any /provider/ endpoint."""
    r1 = await client.get(
        "/api/v1/provider/dashboard/stats", headers=admin_auth_headers
    )
    assert r1.status_code == 403
    r2 = await client.get(
        "/api/v1/provider/team", headers=agent_auth_headers
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_other_provider_settlements_invisible(
    client,
    db_session,
    provider_auth_headers,
    seeded_provider_settlements,
    seeded_tenant,
):
    """A statement under a *different* provider must not appear, even for the
    same tenant."""
    from app.models.settlement import SettlementStatement
    from app.models.tenant import ProviderTenantContract, ServiceProvider

    other_provider = ServiceProvider(
        name="他家律所14",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900014777"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(other_provider)
    db_session.flush()
    other_contract = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=other_provider.id,
        signed_at=datetime.now(UTC),
        service_types=["legal"],
        status="active",
    )
    db_session.add(other_contract)
    db_session.flush()
    other_settle = SettlementStatement(
        contract_id=other_contract.id,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 4, 30, tzinfo=UTC),
        total_amount=Decimal("9999.99"),
        status="DRAFT",
    )
    db_session.add(other_settle)
    db_session.flush()

    resp = await client.get(
        "/api/v1/provider/settlements", headers=provider_auth_headers
    )
    assert resp.status_code == 200
    ids = {it["id"] for it in resp.json()["items"]}
    assert other_settle.id not in ids
    # detail of a non-owned statement → 404
    detail = await client.get(
        f"/api/v1/provider/settlements/{other_settle.id}",
        headers=provider_auth_headers,
    )
    assert detail.status_code == 404
