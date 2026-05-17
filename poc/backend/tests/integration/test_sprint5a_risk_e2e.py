"""Sprint 5a E2E: mock ASR text contains '投诉' →
/ws/calls/{id} receives risk.event (keyword category owner_threat).

Message order for one ASR chunk when keyword matches:
  1. transcript.chunk   — emitted first by _handle_transcript
  2. suggestion.ready   — emitted second (mock LLM fires on first utterance)
  3. risk.event         — emitted third by risk_detector.on_utterance (sync)

Strategy: patch CANNED_TURNS to include a customer utterance with '投诉',
seed a matching RiskKeyword, send exactly FRAMES_PER_CHUNK frames, collect
exactly 3 messages, assert at least one is risk.event.
"""
import os
import pytest

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")

from starlette.testclient import TestClient  # noqa: E402

BYTES_PER_SECOND = 16000 * 2   # 32 000 — matches MockStreamingASRSession
FRAME_SIZE = 3200
FRAMES_PER_CHUNK = BYTES_PER_SECOND // FRAME_SIZE  # 10


@pytest.fixture
def risk_call(db_session, seeded_member_user, seeded_tenant, seeded_case):
    from app.models.call import CallRecord
    from app.core.crypto import encrypt_phone

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13900000001"),
        initiated_by="pc",
        status="pending_dial",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.fixture
def risk_keyword_seed(db_session):
    from app.models.risk import RiskKeyword

    kw = RiskKeyword(
        tenant_id=None,
        category="owner_threat",
        speaker="customer",
        level="L2",
        keyword="投诉",
        is_active=True,
    )
    db_session.add(kw)
    db_session.flush()
    return kw


def test_risk_event_broadcast_on_keyword_hit(
    db_session,
    risk_call,
    risk_keyword_seed,
    seeded_member_user,
    seeded_tenant,
    monkeypatch,
):
    """Agent streams audio containing '投诉' → WS receives risk.event."""
    from app.main import app
    from app.core.db import get_db
    import app.services.streaming_asr_mock as asr_mock_module
    from app.risk import keyword_matcher as km_module
    from app.api import ws_calls as ws_calls_module
    from app.core.security import create_access_token

    # Patch canned turns so the first customer utterance contains "投诉"
    monkeypatch.setattr(
        asr_mock_module,
        "CANNED_TURNS",
        [("customer", "我要去投诉你们"), ("agent", "好的请稍等")],
    )

    # Clear stale caches from other tests
    km_module._matchers.clear()
    ws_calls_module._sessions.clear()

    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    received: list[dict] = []

    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(
                f"/ws/calls/{risk_call.id}?token={token}&role=agent"
            ) as ws:
                ws.send_json({"type": "call.started"})

                fake_frame = b"\x00" * FRAME_SIZE
                for _ in range(FRAMES_PER_CHUNK):
                    ws.send_bytes(fake_frame)

                # One chunk triggers: transcript.chunk + suggestion.ready + risk.event
                for _ in range(3):
                    received.append(ws.receive_json())
    finally:
        app.dependency_overrides.clear()
        km_module._matchers.clear()
        ws_calls_module._sessions.clear()

    risk_events = [m for m in received if m.get("type") == "risk.event"]
    assert len(risk_events) >= 1, (
        f"Expected at least one risk.event; received types: {[m.get('type') for m in received]}"
    )
    evt = risk_events[0]
    assert evt["category"] == "owner_threat"
    assert evt["trigger"] == "keyword"
    assert evt["matched_keyword"] == "投诉"
    assert evt["speaker"] == "customer"
