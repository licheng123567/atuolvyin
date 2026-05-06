"""Sprint 8 T1 — Supervisor Quality Review: GET /reviews + PATCH /reviews/{call_id}"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.core.crypto import encrypt_phone


# ─── shared fixture: one call + analysis that needs review ───────────────────

@pytest.fixture
def seeded_call_needs_review(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.models.call import CallRecord, AnalysisResult

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13811001100"),
        initiated_by="app",
        status="processed",
        started_at=datetime.now(timezone.utc),
        duration_sec=120,
    )
    db_session.add(call)
    db_session.flush()

    analysis = AnalysisResult(
        call_id=call.id,
        summary="AI摘要：客户表示考虑缴款",
        key_segments={"intent": "考虑缴"},
        needs_review=True,
    )
    db_session.add(analysis)
    db_session.flush()
    return call, analysis


@pytest.fixture
def seeded_call_already_labeled(db_session, seeded_tenant, seeded_member_user, seeded_case):
    """Call with analysis already labeled by supervisor."""
    from app.models.call import CallRecord, AnalysisResult

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13811002200"),
        initiated_by="app",
        status="processed",
        started_at=datetime.now(timezone.utc),
        duration_sec=90,
    )
    db_session.add(call)
    db_session.flush()

    analysis = AnalysisResult(
        call_id=call.id,
        summary="AI摘要：客户拒绝",
        key_segments={"intent": "拒绝"},
        needs_review=True,
        supervisor_quality="good",
        supervisor_review_note="通话质量良好",
    )
    db_session.add(analysis)
    db_session.flush()
    return call, analysis


# ─── 1. supervisor can list reviews (needs_review=True calls) ─────────────────

@pytest.mark.asyncio
async def test_supervisor_can_list_reviews(
    client, supervisor_auth_headers, seeded_call_needs_review
):
    call, _ = seeded_call_needs_review
    resp = await client.get(
        "/api/v1/supervisor/reviews",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    call_ids = [item["call_id"] for item in data["items"]]
    assert call.id in call_ids


# ─── 2. only_pending=True (default) should exclude already-labeled calls ──────

@pytest.mark.asyncio
async def test_only_pending_excludes_already_labeled(
    client, supervisor_auth_headers,
    seeded_call_needs_review,
    seeded_call_already_labeled,
):
    labeled_call, _ = seeded_call_already_labeled
    resp = await client.get(
        "/api/v1/supervisor/reviews?only_pending=true",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    call_ids = [item["call_id"] for item in resp.json()["items"]]
    assert labeled_call.id not in call_ids


# ─── 3. only_pending=False should include already-labeled calls ───────────────

@pytest.mark.asyncio
async def test_only_pending_false_includes_all(
    client, supervisor_auth_headers,
    seeded_call_needs_review,
    seeded_call_already_labeled,
):
    labeled_call, _ = seeded_call_already_labeled
    resp = await client.get(
        "/api/v1/supervisor/reviews?only_pending=false",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    call_ids = [item["call_id"] for item in resp.json()["items"]]
    assert labeled_call.id in call_ids


# ─── 4. admin can also access reviews ────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_also_review(
    client, admin_auth_headers, seeded_call_needs_review
):
    call, _ = seeded_call_needs_review
    resp = await client.get(
        "/api/v1/supervisor/reviews",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    call_ids = [item["call_id"] for item in resp.json()["items"]]
    assert call.id in call_ids


# ─── 5. agent is forbidden ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_forbidden(
    client, agent_auth_headers, seeded_call_needs_review
):
    resp = await client.get(
        "/api/v1/supervisor/reviews",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


# ─── 6. PATCH label writes fields correctly ──────────────────────────────────

@pytest.mark.asyncio
async def test_label_review_writes_fields(
    client, supervisor_auth_headers, seeded_call_needs_review, db_session
):
    from app.models.call import AnalysisResult
    call, analysis = seeded_call_needs_review

    resp = await client.patch(
        f"/api/v1/supervisor/reviews/{call.id}",
        json={"quality": "good", "note": "通话规范，语气到位"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supervisor_quality"] == "good"
    assert body["supervisor_review_note"] == "通话规范，语气到位"
    assert body["supervisor_reviewed_at"] is not None

    # DB should also be updated
    db_session.expire(analysis)
    updated = db_session.get(AnalysisResult, analysis.id)
    assert updated.supervisor_quality == "good"
    assert updated.supervisor_review_note == "通话规范，语气到位"
    assert updated.supervisor_reviewed_by is not None
    assert updated.supervisor_reviewed_at is not None


# ─── 7. PATCH with intent_correction updates key_segments ────────────────────

@pytest.mark.asyncio
async def test_label_review_intent_correction_updates_key_segments(
    client, supervisor_auth_headers, seeded_call_needs_review, db_session
):
    from app.models.call import AnalysisResult
    call, analysis = seeded_call_needs_review

    resp = await client.patch(
        f"/api/v1/supervisor/reviews/{call.id}",
        json={
            "quality": "needs_improvement",
            "note": "AI意图识别有误",
            "intent_correction": "拒绝",
        },
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    db_session.expire(analysis)
    updated = db_session.get(AnalysisResult, analysis.id)
    assert updated.key_segments is not None
    assert updated.key_segments.get("intent") == "拒绝"


# ─── 8. PATCH across tenants returns 404 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_label_review_404_for_other_tenant(
    client, db_session, seeded_call_needs_review
):
    """A supervisor from another tenant cannot label a call they don't own."""
    from app.core.security import create_access_token
    from app.core.crypto import encrypt_phone as _enc
    from app.models.user import UserAccount
    from app.models.tenant import Tenant, UserTenantMembership

    # Create a separate tenant + supervisor
    other_tenant = Tenant(
        name="其他物业",
        admin_phone_enc=_enc("13600136001"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other_tenant)
    db_session.flush()

    other_user = UserAccount(
        phone_enc=_enc("13600136002"),
        name="外部督导",
        password_hash="irrelevant",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()

    db_session.add(UserTenantMembership(
        user_id=other_user.id,
        tenant_id=other_tenant.id,
        role="supervisor",
        source_type="INTERNAL",
        is_active=True,
    ))
    db_session.flush()

    other_token = create_access_token({
        "sub": str(other_user.id),
        "user_id": other_user.id,
        "tenant_id": other_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{other_tenant.id}",
    })
    other_headers = {"Authorization": f"Bearer {other_token}"}

    call, _ = seeded_call_needs_review
    resp = await client.patch(
        f"/api/v1/supervisor/reviews/{call.id}",
        json={"quality": "bad", "note": "跨租户尝试"},
        headers=other_headers,
    )
    assert resp.status_code == 404
