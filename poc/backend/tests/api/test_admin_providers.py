"""Sprint 8.1 — admin_providers tests (PRD §3.9).

Covers the property admin's view of partner Service Providers:
listing signed providers, finding available providers, inviting,
adjusting contract & member quotas. All scoped to the admin's tenant.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


# ── fixtures local to this file ─────────────────────────────────────


@pytest.fixture
def approved_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="阳光律师事务所",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13700000010"),
        contact_email="lawyer@example.com",
        description="法务函件 + 诉讼代理",
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def second_approved_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="北辰催收公司",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13700000011"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def pending_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="待审核服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13700000099"),
        is_active=True,
        audit_status="pending",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def signed_contract(db_session, seeded_tenant, approved_provider):
    from app.models.tenant import ProviderTenantContract

    c = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=approved_provider.id,
        signed_at=datetime.now(UTC) - timedelta(days=10),
        expires_at=datetime.now(UTC) + timedelta(days=355),
        service_types=["legal_letter", "litigation"],
        status="active",
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def signed_provider_member(
    db_session, seeded_tenant, approved_provider, signed_contract
):
    """A user belonging to the approved_provider, assigned to seeded_tenant."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13822122222"),
        name="律师王某",
        password_hash=get_password_hash("Lawyer@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    m = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_external",
        source_type="EXTERNAL",
        provider_id=approved_provider.id,
        quota=100,
        access_hours="09:00-18:00",
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    return user


# ── GET /admin/providers ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_signed_providers_empty_for_new_tenant(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get("/api/v1/admin/providers", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_signed_providers_includes_member_count(
    client: AsyncClient,
    signed_contract,
    signed_provider_member,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/providers", headers=admin_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["provider_name"] == "阳光律师事务所"
    assert item["status"] == "active"
    assert item["service_types"] == ["legal_letter", "litigation"]
    assert item["member_count"] == 1


@pytest.mark.asyncio
async def test_list_signed_providers_filters_by_status(
    client: AsyncClient, signed_contract, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/providers?status=terminated", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_signed_providers_search_by_q(
    client: AsyncClient, signed_contract, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/providers?q=阳光", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1


@pytest.mark.asyncio
async def test_list_signed_providers_requires_admin(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/admin/providers", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_signed_providers_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/providers")
    assert resp.status_code == 401


# ── GET /admin/providers/available ───────────────────────────────────


@pytest.mark.asyncio
async def test_list_available_excludes_signed(
    client: AsyncClient,
    signed_contract,
    second_approved_provider,
    pending_provider,
    admin_auth_headers,
):
    resp = await client.get(
        "/api/v1/admin/providers/available", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    # Should include approved-but-not-signed, exclude signed and pending
    assert "北辰催收公司" in names
    assert "阳光律师事务所" not in names
    assert "待审核服务商" not in names


# ── POST /admin/providers/invite ─────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_provider_creates_contract(
    client: AsyncClient, second_approved_provider, admin_auth_headers
):
    body = {
        "provider_id": second_approved_provider.id,
        "service_types": ["collection"],
    }
    resp = await client.post(
        "/api/v1/admin/providers/invite", json=body, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider_id"] == second_approved_provider.id
    assert data["status"] == "active"
    assert data["service_types"] == ["collection"]


@pytest.mark.asyncio
async def test_invite_pending_provider_rejected(
    client: AsyncClient, pending_provider, admin_auth_headers
):
    body = {"provider_id": pending_provider.id, "service_types": ["collection"]}
    resp = await client.post(
        "/api/v1/admin/providers/invite", json=body, headers=admin_auth_headers
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "ERR_PROVIDER_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_invite_unknown_provider_404(
    client: AsyncClient, admin_auth_headers
):
    body = {"provider_id": 999999, "service_types": ["collection"]}
    resp = await client.post(
        "/api/v1/admin/providers/invite", json=body, headers=admin_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invite_duplicate_active_contract_409(
    client: AsyncClient, signed_contract, approved_provider, admin_auth_headers
):
    body = {"provider_id": approved_provider.id, "service_types": ["legal_letter"]}
    resp = await client.post(
        "/api/v1/admin/providers/invite", json=body, headers=admin_auth_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_CONTRACT"


@pytest.mark.asyncio
async def test_invite_requires_at_least_one_service_type(
    client: AsyncClient, second_approved_provider, admin_auth_headers
):
    body = {"provider_id": second_approved_provider.id, "service_types": []}
    resp = await client.post(
        "/api/v1/admin/providers/invite", json=body, headers=admin_auth_headers
    )
    assert resp.status_code == 422


# ── PATCH /admin/providers/{id}/contract ─────────────────────────────


@pytest.mark.asyncio
async def test_patch_contract_updates_expires_and_service_types(
    client: AsyncClient,
    signed_contract,
    approved_provider,
    admin_auth_headers,
):
    new_expires = (datetime.now(UTC) + timedelta(days=730)).isoformat()
    body = {
        "expires_at": new_expires,
        "service_types": ["legal_letter"],
    }
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}/contract",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_types"] == ["legal_letter"]
    # Server may normalise the iso string; just compare prefix
    assert data["expires_at"].startswith(new_expires[:10])


@pytest.mark.asyncio
async def test_patch_contract_can_terminate(
    client: AsyncClient,
    signed_contract,
    approved_provider,
    admin_auth_headers,
):
    body = {"status": "terminated"}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}/contract",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "terminated"


@pytest.mark.asyncio
async def test_patch_contract_unknown_provider_404(
    client: AsyncClient, admin_auth_headers
):
    body = {"status": "terminated"}
    resp = await client.patch(
        "/api/v1/admin/providers/999999/contract",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_contract_invalid_status_422(
    client: AsyncClient, signed_contract, approved_provider, admin_auth_headers
):
    body = {"status": "deleted"}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}/contract",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


# ── GET /admin/providers/{id}/members ────────────────────────────────


@pytest.mark.asyncio
async def test_list_provider_members_includes_quota_and_phone_mask(
    client: AsyncClient,
    signed_contract,
    signed_provider_member,
    approved_provider,
    admin_auth_headers,
):
    resp = await client.get(
        f"/api/v1/admin/providers/{approved_provider.id}/members",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    m = members[0]
    assert m["name"] == "律师王某"
    assert m["phone_masked"] == "138****2222"
    assert m["quota"] == 100
    assert m["access_hours"] == "09:00-18:00"
    assert m["role"] == "agent_external"


@pytest.mark.asyncio
async def test_list_members_for_unsigned_provider_404(
    client: AsyncClient, second_approved_provider, admin_auth_headers
):
    resp = await client.get(
        f"/api/v1/admin/providers/{second_approved_provider.id}/members",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


# ── PATCH /admin/providers/{id}/members/{user_id} ────────────────────


@pytest.mark.asyncio
async def test_patch_member_updates_quota_and_access_hours(
    client: AsyncClient,
    signed_contract,
    signed_provider_member,
    approved_provider,
    admin_auth_headers,
):
    body = {"quota": 250, "access_hours": "10:00-22:00"}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}"
        f"/members/{signed_provider_member.id}",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quota"] == 250
    assert data["access_hours"] == "10:00-22:00"


@pytest.mark.asyncio
async def test_patch_member_can_deactivate(
    client: AsyncClient,
    signed_contract,
    signed_provider_member,
    approved_provider,
    admin_auth_headers,
):
    body = {"is_active": False}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}"
        f"/members/{signed_provider_member.id}",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_patch_member_unknown_user_404(
    client: AsyncClient, signed_contract, approved_provider, admin_auth_headers
):
    body = {"quota": 50}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}/members/999999",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_member_quota_validation(
    client: AsyncClient,
    signed_contract,
    signed_provider_member,
    approved_provider,
    admin_auth_headers,
):
    body = {"quota": -10}
    resp = await client.patch(
        f"/api/v1/admin/providers/{approved_provider.id}"
        f"/members/{signed_provider_member.id}",
        json=body,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422
