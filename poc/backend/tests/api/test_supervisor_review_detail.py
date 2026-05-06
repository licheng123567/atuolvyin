"""Sprint 12.2 — supervisor review detail endpoint tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


def _make_call_with_analysis(
    db_session,
    tenant,
    caller,
    *,
    needs_review=True,
    transcript_text: str | None = "您好，我们物业有事联系您",
    segments: list[dict] | None = None,
):
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord, Transcript

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller.id,
        callee_phone_enc=encrypt_phone("13700000123"),
        initiated_by="app",
        started_at=datetime.now(UTC) - timedelta(minutes=10),
        ended_at=datetime.now(UTC) - timedelta(minutes=8),
        duration_sec=120,
        recording_url="https://storage.example/rec.mp3",
        object_key="calls/1/abc.mp3",
        status="processed",
    )
    db_session.add(call)
    db_session.flush()

    db_session.add(
        AnalysisResult(
            call_id=call.id,
            summary="业主投诉物业管理不到位",
            key_segments={"intent": "complaint"},
            needs_review=needs_review,
        )
    )

    if transcript_text or segments:
        db_session.add(
            Transcript(
                call_id=call.id,
                full_text=transcript_text,
                segments=segments or [
                    {"speaker": "agent", "start_ms": 0, "end_ms": 2000, "text": "您好"},
                    {"speaker": "owner", "start_ms": 2000, "end_ms": 5000, "text": "我有意见"},
                ],
                asr_model="mock",
            )
        )
    db_session.flush()
    return call


def _make_risk(db_session, call, *, level="L2", category="empty_promise", offset_ms=15000):
    from app.models.call import RiskEvent

    r = RiskEvent(
        call_id=call.id,
        level=level,
        category=category,
        trigger_text="您必须今天还，否则我们就上门",
        audio_offset_ms=offset_ms,
        intervention="warn",
    )
    db_session.add(r)
    db_session.flush()
    return r


@pytest.mark.asyncio
async def test_review_detail_returns_full_payload(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_call_with_analysis(db_session, seeded_tenant, seeded_member_user)
    _make_risk(db_session, call, level="L1", offset_ms=5000)
    _make_risk(db_session, call, level="L3", offset_ms=20000)

    resp = await client.get(
        f"/api/v1/supervisor/reviews/{call.id}", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["call_id"] == call.id
    assert data["recording_url"] == "https://storage.example/rec.mp3"
    assert data["transcript_text"] == "您好，我们物业有事联系您"
    assert len(data["transcript_segments"]) == 2
    assert data["asr_model"] == "mock"
    assert len(data["risk_events"]) == 2
    # Sorted by audio_offset_ms asc → L1 (5000) before L3 (20000)
    assert data["risk_events"][0]["level"] == "L1"
    assert data["risk_events"][1]["level"] == "L3"
    assert data["risk_events"][1]["audio_offset_ms"] == 20000


@pytest.mark.asyncio
async def test_review_detail_handles_missing_transcript(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_call_with_analysis(
        db_session, seeded_tenant, seeded_member_user, transcript_text=None,
        segments=[],
    )
    # Remove the transcript entry created above by passing empty segments above won't help — instead
    # we created with segments=[] which still inserts a transcript with empty segments. So the test
    # actually verifies the empty-segments path. Add a separate minimal call without transcript:
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord

    bare_call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000999"),
        initiated_by="app",
        status="processed",
    )
    db_session.add(bare_call)
    db_session.flush()
    db_session.add(
        AnalysisResult(call_id=bare_call.id, needs_review=True, summary="x")
    )
    db_session.flush()

    resp = await client.get(
        f"/api/v1/supervisor/reviews/{bare_call.id}", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript_text"] is None
    assert data["transcript_segments"] == []
    assert data["risk_events"] == []


@pytest.mark.asyncio
async def test_review_detail_unknown_call_404(
    client: AsyncClient, supervisor_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/reviews/999999", headers=supervisor_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_detail_cross_tenant_404(
    client: AsyncClient,
    db_session,
    seeded_member_user,
    supervisor_auth_headers,
):
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant

    other = Tenant(
        name="另一租户",
        admin_phone_enc=encrypt_phone("13900099111"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    call = _make_call_with_analysis(db_session, other, seeded_member_user)

    resp = await client.get(
        f"/api/v1/supervisor/reviews/{call.id}", headers=supervisor_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_detail_requires_supervisor(
    client: AsyncClient, agent_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/reviews/1", headers=agent_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_review_detail_includes_supervisor_label_after_patch(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    """After PATCH-labeling a call, GET detail should reflect the label."""
    call = _make_call_with_analysis(db_session, seeded_tenant, seeded_member_user)

    patch = await client.patch(
        f"/api/v1/supervisor/reviews/{call.id}",
        json={"quality": "needs_improvement", "note": "措辞欠妥"},
        headers=supervisor_auth_headers,
    )
    assert patch.status_code == 200

    detail = await client.get(
        f"/api/v1/supervisor/reviews/{call.id}", headers=supervisor_auth_headers
    )
    assert detail.json()["supervisor_quality"] == "needs_improvement"
    assert detail.json()["supervisor_review_note"] == "措辞欠妥"
