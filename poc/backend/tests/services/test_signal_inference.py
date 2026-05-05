import pytest
from sqlalchemy import select


def test_infer_signal_payment_confirmed_returns_plus1(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    script = ScriptTemplate(
        title="催费话术",
        trigger_intent="经济困难",
        content="建议分期缴纳",
        version=1,
    )
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000001"),
        initiated_by="app",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=60,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id,
        suggestion_id="sug-001",
        user_id=seeded_member_user.id,
        action="adopt",
        suggestion_text="建议分期",
        script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "payment_confirmed", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == 1


def test_infer_signal_complaint_returns_minus1(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    script = ScriptTemplate(title="t", trigger_intent="其他", content="c", version=1)
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000002"),
        initiated_by="app", status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-002",
        user_id=seeded_member_user.id, action="ignore",
        suggestion_text="t", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "complaint", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == -1


def test_infer_signal_unknown_intent_returns_zero(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    script = ScriptTemplate(title="t", trigger_intent="其他", content="c", version=1)
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000003"),
        initiated_by="app", status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-003",
        user_id=seeded_member_user.id, action="adopt",
        suggestion_text="t", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "no_answer", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == 0
