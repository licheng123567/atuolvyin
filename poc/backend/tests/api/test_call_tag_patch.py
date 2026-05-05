import pytest


@pytest.fixture
def seeded_call_with_analysis(db_session, seeded_case, seeded_member_user, seeded_tenant):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, AnalysisResult

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=120,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    analysis = AnalysisResult(
        call_id=call.id,
        summary="客户表示下月发工资再缴费",
        key_segments={"intent": "promise_pay", "promise_date": "2026-05-15"},
        needs_review=False,
    )
    db_session.add(analysis)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_patch_tag_updates_analysis_and_confirms(
    client, agent_auth_headers, seeded_call_with_analysis, db_session,
):
    resp = await client.patch(
        f"/api/v1/calls/{seeded_call_with_analysis.id}/tag",
        json={
            "intent": "promise_pay",
            "promise_date": "2026-05-10",
            "promise_amount": 2400.0,
            "notes": "等下个月发工资",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intent"] == "promise_pay"
    assert body["promise_date"] == "2026-05-10"
    assert body["promise_amount"] == 2400.0
    assert body["user_confirmed_at"] is not None

    db_session.expire_all()
    from app.models.call import CallRecord, AnalysisResult
    from sqlalchemy import select
    call = db_session.execute(
        select(CallRecord).where(CallRecord.id == seeded_call_with_analysis.id)
    ).scalar_one()
    assert call.user_confirmed_at is not None
    analysis = db_session.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == call.id)
    ).scalar_one()
    assert analysis.key_segments["intent"] == "promise_pay"
    assert analysis.key_segments["promise_date"] == "2026-05-10"


@pytest.mark.asyncio
async def test_patch_tag_forbidden_for_other_user(
    client, supervisor_auth_headers, seeded_call_with_analysis,
):
    resp = await client.patch(
        f"/api/v1/calls/{seeded_call_with_analysis.id}/tag",
        json={"intent": "refuse"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_patch_tag_call_not_found(client, agent_auth_headers):
    resp = await client.patch(
        "/api/v1/calls/999999/tag",
        json={"intent": "refuse"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_tag_intent_infers_signal(
    client, agent_auth_headers, seeded_call_with_analysis, db_session, seeded_tenant
):
    """Patching tag with intent=payment_confirmed should infer signal=1 on linked feedbacks."""
    from app.models.call import SuggestionFeedback
    from app.models.script import ScriptTemplate

    # Seed a script template and a feedback row linked to it (pending signal)
    script = ScriptTemplate(
        tenant_id=seeded_tenant.id, title="payment script", trigger_intent="payment_confirmed",
        content="c", version=1
    )
    db_session.add(script)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=seeded_call_with_analysis.id,
        suggestion_id="sug-infer-01",
        user_id=seeded_call_with_analysis.caller_user_id,
        action="adopt",
        suggestion_text="话术内容",
        script_template_id=script.id,
        inferred_signal=None,
    )
    db_session.add(fb)
    db_session.flush()

    resp = await client.patch(
        f"/api/v1/calls/{seeded_call_with_analysis.id}/tag",
        json={"intent": "payment_confirmed"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200

    db_session.expire(fb)
    assert fb.inferred_signal == 1
