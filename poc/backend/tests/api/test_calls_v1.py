import io
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def seeded_device(db_session, seeded_member_user, seeded_tenant):
    from app.models.device import DeviceProfile

    device = DeviceProfile(
        device_id="test-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()
    return device


@pytest.fixture(autouse=True)
def mock_process_call_delay():
    """Prevent Celery from trying to connect to Redis broker in tests."""
    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=None)
    with patch("app.worker.tasks.call_pipeline.process_call", mock_task):
        yield mock_task


async def test_upload_call_creates_record(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    audio_bytes = b"fake audio content"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13899999999",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:02:00+08:00",
            "duration_sec": "120",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "call_id" in data
    assert data["status"] == "uploaded"

    from app.models.call import CallRecord
    call = db_session.get(CallRecord, data["call_id"])
    assert call is not None
    assert call.status == "uploaded"


async def test_upload_wrong_device_returns_403(
    client, agent_auth_headers, seeded_case
):
    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "nonexistent-device",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:01:00+08:00",
            "duration_sec": "60",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_DEVICE_NOT_FOUND"


async def test_upload_quota_exceeded_returns_403(
    client, agent_auth_headers, seeded_device, seeded_case, seeded_tenant, db_session
):
    from app.models.tenant import TenantMinuteUsage

    seeded_tenant.monthly_minute_quota = 10  # 10 minutes
    usage = TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month="2026-04",
        used_minutes=10,  # already at quota
    )
    db_session.add(usage)
    db_session.flush()

    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:02:00+08:00",
            "duration_sec": "60",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_QUOTA_EXCEEDED"


async def test_upload_null_quota_means_unlimited(
    client, agent_auth_headers, seeded_device, seeded_case, seeded_tenant, db_session
):
    seeded_tenant.monthly_minute_quota = None  # unlimited
    db_session.flush()

    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:10:00+08:00",
            "duration_sec": "600",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 201


async def test_list_calls_returns_own_calls(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_device.tenant_id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000001"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get("/api/v1/calls/", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


async def test_get_call_detail_returns_record(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_device.tenant_id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000002"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == call.id
    assert data["transcript"] is None
    assert data["analysis"] is None


async def test_get_call_detail_wrong_user_returns_403(
    client, seeded_device, seeded_case, db_session, seeded_tenant
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    # Create call owned by seeded_device.user_id (member_user)
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000003"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    # Login as a DIFFERENT agent user
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    other = UserAccount(
        phone_enc=encrypt_phone("13600000099"),
        name="其他催收员",
        password_hash=get_password_hash("X"),
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    m = UserTenantMembership(
        user_id=other.id,
        tenant_id=seeded_tenant.id,
        role="agent_internal",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    token = create_access_token({
        "sub": str(other.id),
        "user_id": other.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    other_headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=other_headers)
    assert resp.status_code == 403
