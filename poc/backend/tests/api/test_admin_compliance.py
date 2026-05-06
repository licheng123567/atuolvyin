"""Sprint 8.4 — admin compliance monthly report (PRD §3.13)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _make_call(db_session, tenant, caller_user, *, billable=60, hour=10, day=15):
    """Create a CallRecord on a specific day-of-month and hour (UTC)."""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    now = datetime.now(UTC)
    ts = datetime(now.year, now.month, day, hour, 0, 0, tzinfo=UTC)
    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        billable_duration=billable,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    call.created_at = ts
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


@pytest.mark.asyncio
async def test_list_monthly_reports_returns_default_6_months(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/compliance/monthly", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 6
    # Each row carries a YYYY-MM
    assert all(len(i["year_month"]) == 7 for i in items)


@pytest.mark.asyncio
async def test_list_monthly_can_request_3_months(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/compliance/monthly?months=3", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_get_monthly_report_returns_full_structure(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    _make_risk(db_session, call, level="L2", category="empty_promise")
    _make_risk(db_session, call, level="L3", category="harassment", intervention="terminate")

    now = datetime.now(UTC)
    ym = f"{now.year:04d}-{now.month:02d}"
    resp = await client.get(
        f"/api/v1/admin/compliance/monthly/{ym}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year_month"] == ym
    assert data["tenant_name"] == seeded_tenant.name
    assert data["total_calls"] == 1
    assert data["total_minutes"] == 1
    assert data["total_risk_events"] == 2
    assert data["risk_events_by_level"]["L2"] == 1
    assert data["risk_events_by_level"]["L3"] == 1
    assert data["interrupted_calls"] == 1


@pytest.mark.asyncio
async def test_get_monthly_report_validates_format(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/compliance/monthly/2026-13", headers=admin_auth_headers
    )
    # FastAPI Path pattern returns 422; manual parse would catch as well
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_monthly_report_after_hours_detection(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    # Hour 14 UTC == 22:00 +08, after 21:00 — flagged
    _make_call(db_session, seeded_tenant, seeded_member_user, hour=14)
    # Hour 5 UTC == 13:00 +08 — within window, not flagged
    _make_call(db_session, seeded_tenant, seeded_member_user, hour=5)

    now = datetime.now(UTC)
    ym = f"{now.year:04d}-{now.month:02d}"
    resp = await client.get(
        f"/api/v1/admin/compliance/monthly/{ym}", headers=admin_auth_headers
    )
    data = resp.json()
    assert data["total_calls"] == 2
    assert data["after_hours_calls"] == 1


@pytest.mark.asyncio
async def test_get_monthly_report_dnc_violation_count(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    from app.core.crypto import encrypt_phone
    from app.models.case import CollectionCase, OwnerProfile

    owner = OwnerProfile(
        tenant_id=seeded_tenant.id,
        name="拒接业主",
        phone_enc=encrypt_phone("13822122299"),
        do_not_call=True,
    )
    db_session.add(owner)
    db_session.flush()

    cc = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("100.00"),
    )
    db_session.add(cc)
    db_session.flush()

    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    call.case_id = cc.id
    db_session.flush()

    now = datetime.now(UTC)
    ym = f"{now.year:04d}-{now.month:02d}"
    resp = await client.get(
        f"/api/v1/admin/compliance/monthly/{ym}", headers=admin_auth_headers
    )
    assert resp.json()["do_not_call_violations"] == 1


@pytest.mark.asyncio
async def test_compliance_requires_admin(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/compliance/monthly", headers=ops_auth_headers
    )
    assert resp.status_code == 403
