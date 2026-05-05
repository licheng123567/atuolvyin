from __future__ import annotations

import pytest
from datetime import datetime, timezone


# ─── helpers ────────────────────────────────────────────────────────────────

def _today_utc() -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_call(db_session, seeded_case, seeded_member_user, seeded_tenant):
    """One call record for today, duration_sec=60 (connected)."""
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc="encrypted",
        initiated_by="app",
        started_at=datetime.now(timezone.utc),
        duration_sec=60,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.fixture
def seeded_analysis_promise(db_session, seeded_call):
    """AnalysisResult with key_segments['intent'] == '承诺缴'."""
    from app.models.call import AnalysisResult
    ar = AnalysisResult(
        call_id=seeded_call.id,
        summary="承诺本月底缴纳",
        key_segments={"intent": "承诺缴", "confidence": 0.95},
    )
    db_session.add(ar)
    db_session.flush()
    return ar


@pytest.fixture
def seeded_quota(db_session, seeded_tenant):
    """Tenant with 1000 min quota; TenantMinuteUsage with 200 used."""
    from app.models.tenant import TenantMinuteUsage
    seeded_tenant.monthly_minute_quota = 1000
    db_session.flush()
    year_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month=year_month,
        used_minutes=200,
    )
    db_session.add(usage)
    db_session.flush()
    return usage


@pytest.fixture
def seeded_risk_event(db_session, seeded_call):
    """A risk event linked to seeded_call (within last 7 days)."""
    from app.models.call import RiskEvent
    evt = RiskEvent(
        call_id=seeded_call.id,
        level="L2",
        category="verbal_threat",
        intervention="warn",
    )
    db_session.add(evt)
    db_session.flush()
    return evt


@pytest.fixture
def seeded_suggestion_feedback(db_session, seeded_call, seeded_member_user):
    """SuggestionFeedback with action='adopt'."""
    from app.models.call import SuggestionFeedback
    fb = SuggestionFeedback(
        call_id=seeded_call.id,
        suggestion_id="sug-001",
        user_id=seeded_member_user.id,
        action="adopt",
        suggestion_text="建议分期缴纳",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(fb)
    db_session.flush()
    return fb


# ─── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_get_stats(
    client,
    admin_auth_headers,
    seeded_call,
    seeded_analysis_promise,
    seeded_quota,
    seeded_risk_event,
    seeded_suggestion_feedback,
):
    """Admin role GET /api/v1/admin/dashboard/stats returns 200 with all required fields."""
    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Top-level keys
    assert "today" in body
    assert "minute_quota" in body
    assert "public_pool_count" in body
    assert "risk_alert_count_7d" in body
    assert "top_agents" in body
    assert "script_adoption_trend" in body

    # today stats — we seeded 1 call with duration_sec=60 → connected; 1 promised
    today = body["today"]
    assert today["outbound_count"] >= 1
    assert today["connected_count"] >= 1
    assert today["promised_count"] >= 1
    assert today["recovered_amount"] == 0.0  # placeholder

    # quota
    quota = body["minute_quota"]
    assert quota["used_min"] == 200
    assert quota["total_min"] == 1000
    assert quota["remaining_min"] == 800
    assert quota["warning"] is False  # 200/1000 = 20%, below 80%

    # risk events — seeded 1 event via today's call
    assert body["risk_alert_count_7d"] >= 1

    # trend is 7 entries
    assert len(body["script_adoption_trend"]) == 7


@pytest.mark.asyncio
async def test_non_admin_forbidden(client, agent_auth_headers):
    """agent_internal role GET → 403."""
    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=agent_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_returns_zeros_when_no_data(client, admin_auth_headers):
    """Clean tenant with no data → all zero/empty response."""
    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    today = body["today"]
    assert today["outbound_count"] == 0
    assert today["connected_count"] == 0
    assert today["promised_count"] == 0

    quota = body["minute_quota"]
    assert quota["used_min"] == 0
    assert quota["warning"] is False

    assert body["public_pool_count"] == 0
    assert body["risk_alert_count_7d"] == 0
    assert body["top_agents"] == []
    assert body["script_adoption_trend"] == [0.0] * 7


@pytest.mark.asyncio
async def test_supervisor_can_get_stats(client, supervisor_auth_headers):
    """supervisor role also permitted (ADMIN_ROLES includes supervisor)."""
    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_quota_warning_at_80_percent(db_session, client, admin_auth_headers, seeded_tenant):
    """When used >= 80% quota → warning=True."""
    from app.models.tenant import TenantMinuteUsage
    seeded_tenant.monthly_minute_quota = 1000
    db_session.flush()
    year_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month=year_month,
        used_minutes=850,
    )
    db_session.add(usage)
    db_session.flush()

    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["minute_quota"]["warning"] is True
