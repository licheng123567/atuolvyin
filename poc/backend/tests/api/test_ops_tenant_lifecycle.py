"""Sprint 11 — tenant lifecycle (renew / disable / enable / trial)."""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

# ── Renew ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_renew_extends_expires_at_and_changes_plan(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    new_expires = datetime.now(UTC) + timedelta(days=365)
    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/renew",
        json={
            "expires_at": new_expires.isoformat(),
            "plan": "premium",
            "monthly_minute_quota": 8000,
        },
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "premium"
    assert data["monthly_minute_quota"] == 8000
    assert data["is_trial"] is False  # premium is not trial
    # expires_at should be set (within tolerance)
    returned = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    assert abs((returned - new_expires).total_seconds()) < 5


# ── Disable ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disable_records_reason(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/disable",
        json={"reason": "未续费"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["disabled_reason"] == "未续费"
    assert data["disabled_at"] is not None


@pytest.mark.asyncio
async def test_disable_requires_reason(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/disable",
        json={},  # missing reason
        headers=ops_auth_headers,
    )
    assert resp.status_code == 422


# ── Enable ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enable_clears_disabled_state(
    client: AsyncClient, seeded_tenant, ops_auth_headers, db_session
):
    # First disable it
    seeded_tenant.is_active = False
    seeded_tenant.disabled_reason = "测试停用"
    seeded_tenant.disabled_at = datetime.now(UTC)
    db_session.flush()

    resp = await client.patch(
        f"/api/v1/ops/tenants/{seeded_tenant.id}/enable",
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert data["disabled_reason"] is None
    assert data["disabled_at"] is None


# ── Trial list ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_trial_tenants_only_trial(
    client: AsyncClient, seeded_tenant, ops_auth_headers, db_session
):
    # seeded_tenant has plan='trial' so should appear
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant

    standard = Tenant(
        name="标准版客户",
        admin_phone_enc=encrypt_phone("13900900900"),
        plan="standard",
        is_active=True,
        is_trial=False,
    )
    db_session.add(standard)
    db_session.flush()

    resp = await client.get("/api/v1/ops/tenants/trial", headers=ops_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = {t["id"] for t in data["items"]}
    assert seeded_tenant.id in ids
    assert standard.id not in ids


@pytest.mark.asyncio
async def test_trial_includes_days_remaining(
    client: AsyncClient, seeded_tenant, ops_auth_headers, db_session
):
    seeded_tenant.expires_at = datetime.now(UTC) + timedelta(days=10)
    db_session.flush()

    resp = await client.get("/api/v1/ops/tenants/trial", headers=ops_auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    seeded = next(t for t in items if t["id"] == seeded_tenant.id)
    # days_remaining should be 10 (or 9-11 depending on intra-day rounding)
    assert seeded["days_remaining"] is not None
    assert 9 <= seeded["days_remaining"] <= 11
