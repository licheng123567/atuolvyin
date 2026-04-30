import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_processed_call_for_case(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord, Transcript

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13811112222"),
        status="processed",
        duration_sec=222,
        result_tag="承诺缴",
    )
    db_session.add(call)
    db_session.flush()

    db_session.add(Transcript(
        call_id=call.id,
        full_text="业主称月底缴费。",
        asr_model="mock",
    ))
    db_session.add(AnalysisResult(
        call_id=call.id,
        summary="承诺缴 · 经济困难",
        key_segments={"intent": "承诺缴", "confidence": 0.87, "excuse_category": "经济困难"},
        needs_review=False,
    ))
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_admin_case_detail_includes_call_timeline(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_processed_call_for_case
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_case.id
    assert "calls" in data
    assert "timeline_events" in data
    assert len(data["calls"]) == 1

    call_item = data["calls"][0]
    assert call_item["status"] == "processed"
    assert call_item["result_tag"] == "承诺缴"
    assert call_item["confidence"] == 0.87
    assert call_item["transcript_preview"] == "业主称月底缴费。"


@pytest.mark.asyncio
async def test_admin_case_detail_no_calls_returns_empty_list(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == []
    assert data["timeline_events"] == []
