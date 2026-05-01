# poc/backend/tests/integration/test_sprint4_e2e.py
"""Sprint 4 end-to-end smoke test — mock ASR + mock LLM + mock MiPush.

Full path exercised (entirely in-process, no real Android / DashScope / Xiaomi):

  1. Agent POSTs dial-request → CallRecord created (status=pending_dial)
  2. MiPush mock captures DIAL_REQUEST push notification
  3. Android (simulated) connects WebSocket as agent
  4. Audio frames → mock ASR emits transcript.chunk (10 frames = 1 chunk)
  5. transcript.chunk received by test
  6. call.ended sent → server transitions status to live_ended_pending_analysis

TestClient + frame-bounded receive pattern (mirrors tests/ws/test_ws_calls_e2e.py):
  MockStreamingASRSession emits 1 TranscriptChunk per BYTES_PER_SECOND (32000 B).
  FRAME_SIZE = 3200 B → exactly 10 frames trigger 1 chunk.
  Strategy: send 10 frames → receive_json() once (guaranteed chunk) → done.
  No unbounded drain loop → no hang.
"""
import pytest
from starlette.testclient import TestClient

BYTES_PER_SECOND = 16000 * 2   # 32000 — matches MockStreamingASRSession
FRAME_SIZE = 3200               # bytes per audio frame
FRAMES_PER_CHUNK = BYTES_PER_SECOND // FRAME_SIZE  # 10


@pytest.fixture
def e2e_setup(db_session, seeded_case, seeded_member_user, seeded_tenant):
    """Create assigned case + device with push registration for e2e test."""
    from app.models.device import DeviceProfile

    seeded_case.assigned_to = seeded_member_user.id
    db_session.flush()

    device = DeviceProfile(
        device_id="e2e-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        push_reg_id="reg-e2e-001",
        push_provider="xiaomi",
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()

    return {
        "case": seeded_case,
        "user": seeded_member_user,
        "tenant": seeded_tenant,
    }


def test_full_call_assistance_flow(db_session, e2e_setup):
    """End-to-end: dial-request → MiPush emitted → WS connect → ASR → transcript → call.ended."""
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token
    from app.services import mipush
    from app.models.call import CallRecord
    from sqlalchemy import select

    case = e2e_setup["case"]
    user = e2e_setup["user"]
    tenant = e2e_setup["tenant"]

    # autouse reset_mipush_mock already ran, but reset again for explicitness
    mipush._reset_for_tests()

    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{tenant.id}",
    })
    auth_headers = {"Authorization": f"Bearer {token}"}

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    received: list[dict] = []
    call_id: int | None = None

    try:
        with TestClient(app) as cli:
            # ── Step 1: Agent issues dial-request via PC ──────────────────────
            resp = cli.post(
                "/api/v1/calls/dial-request",
                json={"case_id": case.id},
                headers=auth_headers,
            )
            assert resp.status_code == 201, f"dial-request failed: {resp.text}"
            body = resp.json()
            assert body["status"] == "dispatched", f"unexpected status: {body}"
            call_id = body["call_id"]
            assert isinstance(call_id, int) and call_id > 0

            # ── Step 2: MiPush mock captured the DIAL_REQUEST payload ─────────
            sent = mipush._get_mock_sent()
            assert len(sent) == 1, f"expected 1 push notification, got {len(sent)}"
            pushed = sent[0]
            assert pushed["payload"]["type"] == "DIAL_REQUEST"
            assert pushed["payload"]["call_id"] == call_id
            assert pushed["reg_id"] == "reg-e2e-001"

            # ── Step 3: Android (simulated) connects WebSocket as agent ───────
            with cli.websocket_connect(
                f"/ws/calls/{call_id}?token={token}&role=agent"
            ) as ws:
                ws.send_json({"type": "call.started"})

                # ── Step 4: Feed 10 frames → exactly 1 transcript chunk ───────
                # MockStreamingASRSession emits 1 chunk per 32000 bytes.
                # 10 frames × 3200 B = 32000 B → guaranteed 1 chunk.
                fake_frame = b"\x00" * FRAME_SIZE
                for _ in range(FRAMES_PER_CHUNK):
                    ws.send_bytes(fake_frame)

                # receive_json() returns promptly — message is already buffered
                msg = ws.receive_json()
                received.append(msg)

                # ── Step 5: Agent signals call ended ──────────────────────────
                ws.send_json({"type": "call.ended"})
                # Close cleanly — no more receive_json() after this point

    finally:
        app.dependency_overrides.clear()

    # ── Assertions ────────────────────────────────────────────────────────────
    assert call_id is not None

    # 4a. transcript.chunk was broadcast
    types = [m.get("type") for m in received]
    assert "transcript.chunk" in types, (
        f"Expected transcript.chunk in received messages; got: {received}"
    )

    # 5. call.status transitioned away from pending_dial
    db_session.expire_all()
    call = db_session.execute(
        select(CallRecord).where(CallRecord.id == call_id)
    ).scalar_one()
    assert call.status in (
        "live", "live_ended_pending_analysis", "processed",
    ), f"Unexpected final call status: {call.status!r}"
