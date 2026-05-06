"""Sprint 9.4 / 9.5 — supervisor risk events + team performance tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _make_call(db_session, tenant, caller, *, billable=60, days_ago=0):
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
    if days_ago:
        call.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        db_session.flush()
    return call


def _make_risk(db_session, call, *, level="L2", category="empty_promise", intervention="warn"):
    from app.models.call import RiskEvent

    r = RiskEvent(
        call_id=call.id,
        level=level,
        category=category,
        intervention=intervention,
    )
    db_session.add(r)
    db_session.flush()
    return r


# ── S9.4: risk events timeline ──────────────────────────────────────


@pytest.mark.asyncio
async def test_risk_events_empty_returns_list(
    client: AsyncClient, supervisor_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/risk-events", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_risk_events_lists_recent_with_agent_name(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    _make_risk(db_session, call, level="L3", category="harassment", intervention="terminate")

    resp = await client.get(
        "/api/v1/supervisor/risk-events", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["level"] == "L3"
    assert item["intervention"] == "terminate"
    assert item["agent_name"] == seeded_member_user.name
    assert item["disposition_note"] is None


@pytest.mark.asyncio
async def test_risk_events_filter_by_level(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    _make_risk(db_session, call, level="L1")
    _make_risk(db_session, call, level="L3")

    resp = await client.get(
        "/api/v1/supervisor/risk-events?level=L3", headers=supervisor_auth_headers
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["level"] == "L3"


@pytest.mark.asyncio
async def test_risk_events_excludes_other_tenant(
    client: AsyncClient,
    db_session,
    seeded_member_user,
    supervisor_auth_headers,
):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant

    other = Tenant(
        name="其他租户",
        admin_phone_enc=encrypt_phone("13900099999"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()

    call_other = _make_call(db_session, other, seeded_member_user)
    _make_risk(db_session, call_other, level="L2")

    resp = await client.get(
        "/api/v1/supervisor/risk-events", headers=supervisor_auth_headers
    )
    assert resp.json() == []


@pytest.mark.asyncio
async def test_annotate_risk_event_persists_note(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    risk = _make_risk(db_session, call, level="L2")

    resp = await client.patch(
        f"/api/v1/supervisor/risk-events/{risk.id}",
        json={"note": "已与坐席复盘，提醒注意措辞"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["disposition_note"] == "已与坐席复盘，提醒注意措辞"
    assert data["disposition_at"] is not None


@pytest.mark.asyncio
async def test_annotate_risk_event_unknown_404(
    client: AsyncClient, supervisor_auth_headers
):
    resp = await client.patch(
        "/api/v1/supervisor/risk-events/999999",
        json={"note": "x"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 404


# ── S9.5: team performance ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_team_performance_returns_agents(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    seeded_owner,
    supervisor_auth_headers,
):
    from app.models.case import CollectionCase

    # current period: 2 calls, 1 connected
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=60, days_ago=1)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=0, days_ago=2)
    # previous period: 1 call (used for delta calculation)
    _make_call(db_session, seeded_tenant, seeded_member_user, billable=60, days_ago=10)

    # 1 promised case
    db_session.add(
        CollectionCase(
            tenant_id=seeded_tenant.id,
            owner_id=seeded_owner.id,
            pool_type="public",
            stage="promised",
            amount_owed=Decimal("100.00"),
            assigned_to=seeded_member_user.id,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/supervisor/team-performance?period_days=7",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 7
    item = next(i for i in data["items"] if i["user_id"] == seeded_member_user.id)
    assert item["total_calls"] == 2
    assert item["connected_calls"] == 1
    assert item["promised_cases"] == 1
    assert item["conversion_rate"] == pytest.approx(0.5, abs=1e-3)
    # current 2 vs previous 1 → +100% delta
    assert item["delta_vs_previous"] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_team_performance_requires_supervisor(
    client: AsyncClient, agent_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/team-performance", headers=agent_auth_headers
    )
    assert resp.status_code == 403
