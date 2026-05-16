# poc/backend/tests/ws/test_ws_calls_e2e.py
"""
E2E test: agent connects over WebSocket, streams audio, receives transcript chunks.

TestClient + WebSocket receive_json() behaviour:
  starlette TestClient uses anyio memory-object-streams with infinite capacity.
  send_bytes() enqueues a message; the server processes messages asynchronously
  in the same portal.  receive_json() blocks the test thread until the server
  pushes a message into the send stream.

  MockStreamingASRSession emits 1 TranscriptChunk per BYTES_PER_SECOND (32000 B).
  FRAME_SIZE = 3200 B → 10 frames trigger exactly 1 chunk.

  Strategy: send frames one-at-a-time. After every 10th frame a chunk is
  guaranteed; call receive_json() exactly once at that point.  Collect
  EXPECTED_CHUNKS chunks this way, then close the WS cleanly.  No unbounded
  drain loop → no hang.
"""
import pytest
from starlette.testclient import TestClient

BYTES_PER_SECOND = 16000 * 2   # 32000 — matches MockStreamingASRSession
FRAME_SIZE = 3200               # bytes per audio frame
FRAMES_PER_CHUNK = BYTES_PER_SECOND // FRAME_SIZE  # 10
EXPECTED_CHUNKS = 2             # we send 20 frames → 2 chunks


@pytest.fixture
def call_for_member(db_session, seeded_member_user, seeded_tenant, seeded_case):
    from app.models.call import CallRecord
    from app.core.crypto import encrypt_phone

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        status="pending_dial",
    )
    db_session.add(call)
    db_session.flush()
    return call


def test_ws_agent_streams_audio_receives_transcript(
    db_session,
    call_for_member,
    seeded_member_user,
    seeded_tenant,
    agent_auth_headers,
):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

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
                f"/ws/calls/{call_for_member.id}?token={token}&role=agent"
            ) as ws:
                ws.send_json({"type": "call.started"})

                fake_frame = b"\x00" * FRAME_SIZE
                chunks_collected = 0

                for i in range(1, EXPECTED_CHUNKS * FRAMES_PER_CHUNK + 1):
                    ws.send_bytes(fake_frame)
                    # After every FRAMES_PER_CHUNK frames a chunk has been emitted.
                    # Collect it immediately — receive_json() will return promptly
                    # because the message is already in the server's send buffer.
                    if i % FRAMES_PER_CHUNK == 0 and chunks_collected < EXPECTED_CHUNKS:
                        msg = ws.receive_json()
                        received.append(msg)
                        chunks_collected += 1

                # Close cleanly — server will receive disconnect and exit its loop.
                # Do NOT call receive_json() after this point; the server may not
                # send any more messages before disconnect, causing an infinite wait.

    finally:
        app.dependency_overrides.clear()

    assert any(m.get("type") == "transcript.chunk" for m in received), (
        f"Expected at least one transcript.chunk in {len(received)} messages; got: {received}"
    )
    assert chunks_collected >= 1, "Should have collected at least one chunk"
