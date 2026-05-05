import os
from contextlib import contextmanager

import pytest

os.environ.setdefault("ASR_BACKEND", "mock")
os.environ.setdefault("LLM_BACKEND", "mock")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "True")


def _make_feedbacks(db, call_id, script_id, user_id, adopts: int, ignores: int, signals: list[int]):
    from app.models.call import SuggestionFeedback
    for i in range(adopts):
        fb = SuggestionFeedback(
            call_id=call_id, suggestion_id=f"s-a-{i}-{script_id}",
            user_id=user_id, action="adopt",
            suggestion_text="t", script_template_id=script_id,
            inferred_signal=signals[i] if i < len(signals) else 0,
        )
        db.add(fb)
    for i in range(ignores):
        fb = SuggestionFeedback(
            call_id=call_id, suggestion_id=f"s-i-{i}-{script_id}",
            user_id=user_id, action="ignore",
            suggestion_text="t", script_template_id=script_id,
        )
        db.add(fb)
    db.flush()


@pytest.fixture
def grading_setup(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    from app.models.script import ScriptTemplate

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700009999"),
        initiated_by="app", status="processed",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(call)
    db_session.flush()
    return call, seeded_member_user


def test_grade_a_script(db_session, grading_setup):
    call, user = grading_setup
    from unittest.mock import patch
    import app.worker.tasks.script_grading as grading_module
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(title="高质量话术", trigger_intent="经济困难",
                            content="c", version=1, is_active=True, usage_count=30)
    db_session.add(script)
    db_session.flush()
    # 25 adopts / 5 ignores = adoption_rate=0.833 → A
    _make_feedbacks(db_session, call.id, script.id, user.id, 25, 5, [1]*10)
    db_session.commit()

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(grading_module, "_get_db", _mock_db):
        grading_module.compute_script_grades()

    db_session.expire(script)
    assert script.score_grade == "A"
    assert script.adoption_rate is not None


def test_grade_d_auto_disables(db_session, grading_setup):
    call, user = grading_setup
    from unittest.mock import patch
    import app.worker.tasks.script_grading as grading_module
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(title="低效话术", trigger_intent="其他",
                            content="c", version=1, is_active=True, usage_count=25)
    db_session.add(script)
    db_session.flush()
    # 3 adopts / 22 ignores = adoption_rate=0.12 → D，usage_count>=20 → 自动禁用
    _make_feedbacks(db_session, call.id, script.id, user.id, 3, 22, [])
    db_session.commit()

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(grading_module, "_get_db", _mock_db):
        grading_module.compute_script_grades()

    db_session.expire(script)
    assert script.score_grade == "D"
    assert script.is_active is False
