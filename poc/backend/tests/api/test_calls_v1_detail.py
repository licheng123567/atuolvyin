import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_processed_call(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord, Transcript

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800005678"),
        status="processed",
        object_key="calls/test/processed.mp3",
    )
    db_session.add(call)
    db_session.flush()

    db_session.add(Transcript(
        call_id=call.id,
        full_text="[坐席] 您好。\n[业主] 知道了月底缴。",
        segments=[{"speaker": 0, "start_ms": 0, "end_ms": 3000, "text": "您好。"}],
        asr_model="mock",
    ))
    db_session.add(AnalysisResult(
        call_id=call.id,
        summary="承诺缴 · 经济困难",
        key_segments={
            "intent": "承诺缴",
            "promise_date": "2026-04-30",
            "excuse_category": "经济困难",
            "compliance_disclosed": True,
            "risk_keywords": [],
            "confidence": 0.85,
            "needs_review": False,
        },
        followup_suggestion="2026-04-30",
        prompt_version="v1",
        llm_model="mock",
        needs_review=False,
    ))
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_call_detail_with_transcript_and_analysis(
    client: AsyncClient, agent_auth_headers, seeded_processed_call
):
    resp = await client.get(
        f"/api/v1/calls/{seeded_processed_call.id}", headers=agent_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"

    t = data["transcript"]
    assert t is not None
    assert "您好" in t["full_text"]
    assert len(t["segments"]) == 1
    assert t["asr_model"] == "mock"

    a = data["analysis"]
    assert a is not None
    assert a["intent"] == "承诺缴"
    assert a["confidence"] == 0.85
    assert a["promise_date"] == "2026-04-30"
    assert a["needs_review"] is False


@pytest.mark.asyncio
async def test_call_detail_no_transcript_returns_null(
    client: AsyncClient, agent_auth_headers, seeded_member_user, seeded_tenant, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800009999"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] is None
    assert data["analysis"] is None
