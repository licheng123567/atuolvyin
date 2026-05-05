import pytest
from datetime import datetime, timezone


@pytest.fixture
def seeded_feedback_with_script(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate

    script = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="测试话术",
        trigger_intent="其他",
        content="话术内容",
        version=1,
    )
    db_session.add(script)

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000099"),
        initiated_by="app", status="processed",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-sup-01",
        user_id=seeded_member_user.id, action="adopt",
        suggestion_text="话术内容", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()
    return fb


@pytest.mark.asyncio
async def test_get_labels_list(client, supervisor_auth_headers, seeded_feedback_with_script):
    resp = await client.get("/api/v1/supervisor/script-labels", headers=supervisor_auth_headers)
    assert resp.status_code == 200
    ids = [item["feedback_id"] for item in resp.json()]
    assert seeded_feedback_with_script.id in ids


@pytest.mark.asyncio
async def test_post_good_label(client, supervisor_auth_headers, seeded_feedback_with_script, db_session):
    from app.models.call import SuggestionFeedback
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "good"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.expire(seeded_feedback_with_script)
    assert seeded_feedback_with_script.supervisor_label == "good"


@pytest.mark.asyncio
async def test_post_bad_label_requires_note(client, supervisor_auth_headers, seeded_feedback_with_script):
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "bad"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_bad_label_with_note(client, supervisor_auth_headers, seeded_feedback_with_script, db_session):
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "bad", "note": "话术效果差"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    db_session.expire(seeded_feedback_with_script)
    assert seeded_feedback_with_script.supervisor_label == "bad"
    assert seeded_feedback_with_script.supervisor_note == "话术效果差"
