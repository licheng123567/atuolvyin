"""Sprint 11.4 — Agent personal performance dashboard tests."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _make_call(db_session, tenant, caller, *, billable=60):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        billable_duration=billable,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_my_performance_zero_state(
    client: AsyncClient, agent_auth_headers, seeded_member_user
):
    resp = await client.get(
        "/api/v1/agent/me/performance", headers=agent_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == seeded_member_user.id
    assert data["month_calls"] == 0
    assert data["month_connected"] == 0
    assert data["conversion_rate"] is None
    assert data["rank_in_tenant"] == 0


@pytest.mark.asyncio
async def test_my_performance_aggregates_calls(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    seeded_owner,
    agent_auth_headers,
):
    from app.models.case import CollectionCase

    _make_call(db_session, seeded_tenant, seeded_member_user, billable=60)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=0)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=120)

    db_session.add(
        CollectionCase(
            tenant_id=seeded_tenant.id,
            owner_id=seeded_owner.id,
            pool_type="public",
            stage="promised",
            amount_owed=Decimal("3000.00"),
            assigned_to=seeded_member_user.id,
        )
    )
    db_session.add(
        CollectionCase(
            tenant_id=seeded_tenant.id,
            owner_id=seeded_owner.id,
            pool_type="public",
            stage="paid",
            amount_owed=Decimal("1500.00"),
            assigned_to=seeded_member_user.id,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/agent/me/performance", headers=agent_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["month_calls"] == 3
    assert data["month_connected"] == 2
    assert data["month_promised_cases"] == 1
    assert data["month_paid_cases"] == 1
    assert Decimal(data["month_paid_amount"]) == Decimal("1500.00")
    assert data["conversion_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert data["rank_in_tenant"] == 1


@pytest.mark.asyncio
async def test_my_performance_excludes_other_tenant_calls(
    client: AsyncClient,
    db_session,
    seeded_member_user,
    agent_auth_headers,
):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant

    other = Tenant(
        name="另一租户",
        admin_phone_enc=encrypt_phone("13900088888"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    _make_call(db_session, other, seeded_member_user)

    resp = await client.get(
        "/api/v1/agent/me/performance", headers=agent_auth_headers
    )
    assert resp.json()["month_calls"] == 0


@pytest.mark.asyncio
async def test_my_performance_requires_agent(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/agent/me/performance", headers=admin_auth_headers
    )
    assert resp.status_code == 403
