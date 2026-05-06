"""Sprint 15 — Cost dashboard tests."""
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cost_dashboard_returns_shape(
    client: AsyncClient, seeded_tenant, super_auth_headers, db_session
):
    # Seed quota + usage on the existing tenant
    from app.models.tenant import TenantMinuteUsage
    seeded_tenant.monthly_minute_quota = 1000
    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.add(
        TenantMinuteUsage(
            tenant_id=seeded_tenant.id,
            year_month=ym,
            used_minutes=200,
            quota_at_time=1000,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/super/cost/dashboard", headers=super_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_quota_pool"] >= 1000
    assert data["total_used_this_month"] >= 200
    assert isinstance(data["tenant_ranking"], list)
    assert any(r["tenant_id"] == seeded_tenant.id for r in data["tenant_ranking"])
    assert isinstance(data["monthly_trend"], list)
    assert len(data["monthly_trend"]) == 6


@pytest.mark.asyncio
async def test_cost_dashboard_ranking_utilization(
    client: AsyncClient, seeded_tenant, super_auth_headers, db_session
):
    from app.models.tenant import TenantMinuteUsage
    seeded_tenant.monthly_minute_quota = 500
    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.add(
        TenantMinuteUsage(
            tenant_id=seeded_tenant.id,
            year_month=ym,
            used_minutes=125,
            quota_at_time=500,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/super/cost/dashboard", headers=super_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    me = next(r for r in data["tenant_ranking"] if r["tenant_id"] == seeded_tenant.id)
    assert me["used_minutes"] == 125
    assert me["quota"] == 500
    assert abs(me["utilization_pct"] - 25.0) < 0.01


@pytest.mark.asyncio
async def test_cost_dashboard_role_guard(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/super/cost/dashboard", headers=ops_auth_headers
    )
    assert resp.status_code == 403
