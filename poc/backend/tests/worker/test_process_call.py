from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture
def seeded_call(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()
    return call


def test_process_call_sets_status_queued(seeded_call, db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()  # make changes visible without a real COMMIT

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call.id)

    db_session.refresh(seeded_call)
    assert seeded_call.status == "queued"


def test_process_call_nonexistent_id_is_noop(db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(999999999)  # should not raise
