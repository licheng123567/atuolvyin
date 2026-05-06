"""Sprint 11 — platform_ops Service Provider tests."""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="测试律师事务所",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13700000001"),
        contact_email="lawyer@example.com",
        description="提供法务函件",
        monthly_minute_quota=2000,
        is_active=True,
        audit_status="pending",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def approved_provider(db_session):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="已审核服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13700000002"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


# ── List ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_providers_basic(
    client: AsyncClient, seeded_provider, ops_auth_headers
):
    resp = await client.get("/api/v1/ops/providers", headers=ops_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(p["id"] == seeded_provider.id for p in data["items"])
    item = next(p for p in data["items"] if p["id"] == seeded_provider.id)
    assert item["admin_phone_masked"] == "137****0001"
    assert item["audit_status"] == "pending"


@pytest.mark.asyncio
async def test_filter_providers_by_audit_status(
    client: AsyncClient, seeded_provider, approved_provider, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/providers",
        params={"audit_status": "approved"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(p["id"] == approved_provider.id for p in items)
    assert all(p["audit_status"] == "approved" for p in items)


# ── Create ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_provider_starts_pending(client: AsyncClient, ops_auth_headers):
    payload = {
        "name": "新服务商",
        "provider_type": "both",
        "admin_phone": "13888888888",
        "contact_email": "admin@example.com",
        "description": "兼营法务和催收",
        "monthly_minute_quota": 5000,
    }
    resp = await client.post(
        "/api/v1/ops/providers", json=payload, headers=ops_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["audit_status"] == "pending"
    assert data["audit_at"] is None
    assert data["audit_reason"] is None
    assert data["admin_phone_masked"] == "138****8888"
    assert data["provider_type"] == "both"
    assert data["is_active"] is True


# ── Audit ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_approve(
    client: AsyncClient, seeded_provider, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/audit",
        json={"decision": "approved"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["audit_status"] == "approved"
    assert data["audit_at"] is not None


@pytest.mark.asyncio
async def test_audit_reject_requires_reason(
    client: AsyncClient, seeded_provider, ops_auth_headers
):
    # No reason → 422
    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/audit",
        json={"decision": "rejected"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 422

    # With reason → 200
    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/audit",
        json={"decision": "rejected", "reason": "资质不全"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["audit_status"] == "rejected"
    assert data["audit_reason"] == "资质不全"


@pytest.mark.asyncio
async def test_audit_rejects_non_pending(
    client: AsyncClient, approved_provider, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/providers/{approved_provider.id}/audit",
        json={"decision": "approved"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_INVALID_TRANSITION"


# ── Detail with contracts ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_provider_detail_with_contracts(
    client: AsyncClient,
    db_session,
    approved_provider,
    seeded_tenant,
    ops_auth_headers,
):
    from app.models.tenant import ProviderTenantContract

    contract = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=approved_provider.id,
        signed_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
        service_types=["collection"],
        status="active",
    )
    db_session.add(contract)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/ops/providers/{approved_provider.id}", headers=ops_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == approved_provider.id
    assert "contracts" in data
    assert len(data["contracts"]) == 1
    c = data["contracts"][0]
    assert c["tenant_id"] == seeded_tenant.id
    assert c["tenant_name"] == seeded_tenant.name
    assert c["status"] == "active"
    assert "collection" in c["service_types"]


# ── Patch fields ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_provider_fields(
    client: AsyncClient, seeded_provider, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}",
        json={
            "name": "改名后的服务商",
            "description": "新描述",
            "monthly_minute_quota": 9999,
        },
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "改名后的服务商"
    assert data["description"] == "新描述"
    assert data["monthly_minute_quota"] == 9999


# ── Toggle active ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_toggle_provider_active(
    client: AsyncClient, seeded_provider, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/active",
        json={"is_active": False},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/active",
        json={"is_active": True},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


# ── AuthZ ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_ops_forbidden(
    client: AsyncClient, seeded_provider, admin_auth_headers
):
    # Admin role cannot access platform_ops endpoints
    resp = await client.get("/api/v1/ops/providers", headers=admin_auth_headers)
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/ops/providers",
        json={
            "name": "x",
            "provider_type": "legal",
            "admin_phone": "13800000000",
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/v1/ops/providers/{seeded_provider.id}/audit",
        json={"decision": "approved"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403
