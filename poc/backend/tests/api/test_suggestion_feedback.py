import pytest


@pytest.fixture
def seeded_call_processed(db_session, seeded_case, seeded_member_user, seeded_tenant):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=60,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_suggestion_feedback_inserts_row(client, agent_auth_headers, seeded_call_processed, db_session):
    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-abc/feedback",
        json={"action": "adopt"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text

    from app.models.call import SuggestionFeedback
    from sqlalchemy import select
    rows = db_session.execute(
        select(SuggestionFeedback).where(SuggestionFeedback.call_id == seeded_call_processed.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].suggestion_id == "sug-abc"
    assert rows[0].action == "adopt"


@pytest.mark.asyncio
async def test_suggestion_feedback_idempotent(client, agent_auth_headers, seeded_call_processed):
    body = {"action": "ignore"}
    resp1 = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-xyz/feedback",
        json=body, headers=agent_auth_headers,
    )
    assert resp1.status_code == 201
    resp2 = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-xyz/feedback",
        json=body, headers=agent_auth_headers,
    )
    assert resp2.status_code == 200  # idempotent — already recorded


@pytest.mark.asyncio
async def test_suggestion_feedback_other_user_forbidden(
    client, supervisor_auth_headers, seeded_call_processed,
):
    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-1/feedback",
        json={"action": "adopt"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_feedback_with_script_template_id_increments_usage(
    client, agent_auth_headers, seeded_call_processed, db_session, seeded_tenant
):
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(
        tenant_id=seeded_tenant.id, title="t", trigger_intent="其他", content="c", version=1
    )
    db_session.add(script)
    db_session.flush()

    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-st-01/feedback",
        json={"action": "adopt", "script_template_id": script.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201

    db_session.expire(script)
    assert script.usage_count == 1
