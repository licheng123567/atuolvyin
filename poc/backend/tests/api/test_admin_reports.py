"""Sprint 8.3 — admin reports overview tests (PRD §3.12)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _make_case(db_session, tenant, owner, *, stage="new", assigned_to=None):
    from app.models.case import CollectionCase

    c = CollectionCase(
        tenant_id=tenant.id,
        owner_id=owner.id,
        pool_type="public",
        stage=stage,
        amount_owed=Decimal("3000.00"),
        priority_score=100,
        assigned_to=assigned_to,
    )
    db_session.add(c)
    db_session.flush()
    return c


def _make_call(db_session, tenant, caller_user, *, billable=60, created_at=None):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        billable_duration=billable,
        status="processed",
    )
    if created_at:
        call.created_at = created_at
    db_session.add(call)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_overview_returns_structure(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/reports/overview", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 30
    # Funnel always returns 5 fixed stages
    stages = [f["stage"] for f in data["funnel"]]
    assert stages == ["new", "contacted", "promised", "paid", "closed"]
    assert data["agent_performance"] == []
    assert data["objection_distribution"] == []
    assert data["promise_followup"]["rate"] is None


@pytest.mark.asyncio
async def test_overview_funnel_counts_cases_per_stage(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_owner,
    admin_auth_headers,
):
    _make_case(db_session, seeded_tenant, seeded_owner, stage="new")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="new")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="promised")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="paid")

    resp = await client.get(
        "/api/v1/admin/reports/overview", headers=admin_auth_headers
    )
    funnel = {f["stage"]: f["count"] for f in resp.json()["funnel"]}
    assert funnel["new"] == 2
    assert funnel["promised"] == 1
    assert funnel["paid"] == 1
    assert funnel["closed"] == 0


@pytest.mark.asyncio
async def test_overview_agent_performance_aggregates_calls(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_owner,
    seeded_member_user,
    admin_auth_headers,
):
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=30)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=0)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=120)
    _make_case(
        db_session,
        seeded_tenant,
        seeded_owner,
        stage="promised",
        assigned_to=seeded_member_user.id,
    )

    resp = await client.get(
        "/api/v1/admin/reports/overview", headers=admin_auth_headers
    )
    perf = resp.json()["agent_performance"]
    assert len(perf) == 1
    row = perf[0]
    assert row["user_id"] == seeded_member_user.id
    assert row["total_calls"] == 3
    assert row["connected_calls"] == 2
    assert row["promised_cases"] == 1
    assert row["conversion_rate"] == pytest.approx(1 / 3, abs=1e-3)


@pytest.mark.asyncio
async def test_overview_excludes_old_calls(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    _make_call(
        db_session,
        seeded_tenant,
        seeded_member_user,
        created_at=datetime.now(UTC) - timedelta(days=100),
    )

    resp = await client.get(
        "/api/v1/admin/reports/overview?period_days=7",
        headers=admin_auth_headers,
    )
    perf = resp.json()["agent_performance"]
    assert perf == []


@pytest.mark.asyncio
async def test_overview_promise_followup_rate(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_owner,
    admin_auth_headers,
):
    _make_case(db_session, seeded_tenant, seeded_owner, stage="promised")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="promised")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="paid")
    _make_case(db_session, seeded_tenant, seeded_owner, stage="new")  # excluded

    resp = await client.get(
        "/api/v1/admin/reports/overview", headers=admin_auth_headers
    )
    fu = resp.json()["promise_followup"]
    assert fu["total_promised"] == 3  # promised + paid
    assert fu["total_paid"] == 1
    assert fu["rate"] == pytest.approx(1 / 3, abs=1e-3)


@pytest.mark.asyncio
async def test_overview_requires_admin(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/reports/overview", headers=ops_auth_headers
    )
    assert resp.status_code == 403
