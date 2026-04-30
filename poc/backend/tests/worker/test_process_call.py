import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture
def seeded_call_with_recording(db_session, seeded_tenant, seeded_member_user, seeded_case):
    """Creates a CallRecord with object_key and writes a fake audio file to test storage."""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    object_key = f"calls/{seeded_tenant.id}/test3b_{seeded_member_user.id}.mp3"
    storage_root = os.environ.get("LOCAL_STORAGE_ROOT", "/tmp/autoluyin_test_recordings")
    file_path = os.path.join(storage_root, object_key)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(b"ID3\x00" + b"\x00" * 100)  # minimal fake MP3

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        status="uploaded",
        object_key=object_key,
    )
    db_session.add(call)
    db_session.flush()

    yield call

    # cleanup file (DB rollback handles DB state)
    try:
        os.unlink(file_path)
    except OSError:
        pass


def test_process_call_full_pipeline(seeded_call_with_recording, db_session):
    """Full pipeline: mock ASR + mock LLM → status=processed, Transcript + AnalysisResult created."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from sqlalchemy import select
    from app.models.call import Transcript, AnalysisResult

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)

    db_session.refresh(seeded_call_with_recording)
    assert seeded_call_with_recording.status == "processed"

    transcript = db_session.execute(
        select(Transcript).where(Transcript.call_id == seeded_call_with_recording.id)
    ).scalar_one_or_none()
    assert transcript is not None
    assert transcript.full_text is not None
    assert transcript.asr_model == "mock"

    analysis = db_session.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == seeded_call_with_recording.id)
    ).scalar_one_or_none()
    assert analysis is not None
    assert analysis.key_segments is not None
    assert "intent" in analysis.key_segments
    assert analysis.needs_review is False


def test_process_call_idempotent_on_retry(seeded_call_with_recording, db_session):
    """Running process_call twice does not create duplicate Transcript/AnalysisResult."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from sqlalchemy import select, func
    from app.models.call import Transcript, AnalysisResult

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)
    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)

    count_t = db_session.execute(
        select(func.count()).select_from(Transcript).where(Transcript.call_id == seeded_call_with_recording.id)
    ).scalar_one()
    count_a = db_session.execute(
        select(func.count()).select_from(AnalysisResult).where(AnalysisResult.call_id == seeded_call_with_recording.id)
    ).scalar_one()
    assert count_t == 1
    assert count_a == 1


def test_process_call_no_object_key_sets_failed(db_session, seeded_tenant, seeded_member_user, seeded_case):
    """Call with no object_key: pipeline marks status=failed and returns."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800001111"),
        status="uploaded",
        object_key=None,
    )
    db_session.add(call)
    db_session.flush()

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(call.id)

    db_session.refresh(call)
    assert call.status == "failed"


def test_process_call_nonexistent_id_is_noop(db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(999999999)  # should not raise
