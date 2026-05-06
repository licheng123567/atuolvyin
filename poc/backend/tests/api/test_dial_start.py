"""Sprint 14.2 — dial-start + heartbeat + 实时通话墙 (PRD §10.1 / §11.6).

7 项验收：
  1. dial-start 创建 status='dialing' + recording_mode 冻结
  2. 跨租户 / 未分配案件 → 404 / 403
  3. 同一 caller 并发拨号 → 409
  4. 软配额 < 3 分钟 → 403 ERR_QUOTA_EXHAUSTED
  5. heartbeat 更新 last_heartbeat_at
  6. cleanup_stale_calls 把 90s+ 无心跳的通话标 aborted
  7. /supervisor/live-calls 返回当前租户进行中通话
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


# ── 1. dial-start 基础路径 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_dial_start_creates_dialing_call(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    seeded_tenant,
    agent_auth_headers,
):
    resp = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "dialing"
    assert data["recording_mode"] in ("live", "post")
    assert data["call_id"] > 0

    from app.models.call import CallRecord
    call = db_session.get(CallRecord, data["call_id"])
    assert call.status == "dialing"
    assert call.recording_mode == data["recording_mode"]
    assert call.last_heartbeat_at is not None


# ── 2. 跨租户 / 未分配 → 404 / 403 ──────────────────────────────


@pytest.mark.asyncio
async def test_dial_start_unknown_case_404(client, agent_auth_headers):
    resp = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": 999999, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dial_start_unassigned_case_403(
    client, db_session, seeded_case, seeded_supervisor_user, agent_auth_headers
):
    # 把 case 分配给另一个用户（supervisor），且非 public pool
    seeded_case.assigned_to = seeded_supervisor_user.id
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


# ── 3. 同一 caller 并发 → 409 ───────────────────────────────────


@pytest.mark.asyncio
async def test_dial_start_concurrent_caller_returns_409(
    client, db_session, seeded_assigned_case, agent_auth_headers
):
    r1 = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-2"},
        headers=agent_auth_headers,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "ERR_ACTIVE_CALL_EXISTS"


# ── 4. 软配额拦截 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dial_start_blocked_when_quota_below_threshold(
    client, db_session, seeded_assigned_case, seeded_tenant, agent_auth_headers
):
    from app.models.tenant import TenantMinuteUsage
    seeded_tenant.monthly_minute_quota = 100
    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.add(TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month=ym,
        used_minutes=98,  # 剩 2 < SOFT_QUOTA_MIN_REMAINING=3
        post_minutes=98,
    ))
    db_session.commit()
    resp = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_QUOTA_EXHAUSTED"


# ── 5. heartbeat 更新时间戳 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_updates_timestamp(
    client, db_session, seeded_assigned_case, agent_auth_headers
):
    r = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    call_id = r.json()["call_id"]

    from app.models.call import CallRecord
    call = db_session.get(CallRecord, call_id)
    original_ts = call.last_heartbeat_at

    # 拨快时钟前不能直接调（毫秒级），sleep 0.05 秒
    import time as _t; _t.sleep(0.05)

    h = await client.post(
        f"/api/v1/calls/{call_id}/heartbeat", headers=agent_auth_headers
    )
    assert h.status_code == 200, h.text
    db_session.expire_all()
    call = db_session.get(CallRecord, call_id)
    assert call.last_heartbeat_at > original_ts


@pytest.mark.asyncio
async def test_heartbeat_rejects_non_active_call(
    client, db_session, seeded_assigned_case, seeded_member_user, agent_auth_headers
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=seeded_assigned_case.tenant_id,
        case_id=seeded_assigned_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="processed",  # 已结束
    )
    db_session.add(call); db_session.commit()
    resp = await client.post(
        f"/api/v1/calls/{call.id}/heartbeat", headers=agent_auth_headers
    )
    assert resp.status_code == 409


# ── 6. heartbeat 超时清理 ────────────────────────────────────────


def test_cleanup_stale_calls_aborts_old_dialing(
    db_session, seeded_assigned_case, seeded_member_user
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    from app.services.call_lifecycle import cleanup_stale_calls, HEARTBEAT_TIMEOUT_SEC

    long_ago = datetime.now(UTC) - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC + 30)
    stale = CallRecord(
        tenant_id=seeded_assigned_case.tenant_id,
        case_id=seeded_assigned_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="dialing",
        recording_mode="live",
        started_at=long_ago,
        last_heartbeat_at=long_ago,
    )
    db_session.add(stale); db_session.commit()

    aborted = cleanup_stale_calls(db_session)
    assert stale.id in aborted
    db_session.expire(stale)
    assert stale.status == "aborted"
    assert stale.ended_at is not None


def test_cleanup_skips_recently_alive(db_session, seeded_assigned_case, seeded_member_user):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    from app.services.call_lifecycle import cleanup_stale_calls

    fresh = CallRecord(
        tenant_id=seeded_assigned_case.tenant_id,
        case_id=seeded_assigned_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="live",
        recording_mode="live",
        started_at=datetime.now(UTC),
        last_heartbeat_at=datetime.now(UTC),  # 刚刚
    )
    db_session.add(fresh); db_session.commit()

    aborted = cleanup_stale_calls(db_session)
    assert fresh.id not in aborted


# ── 7. /supervisor/live-calls ───────────────────────────────────


@pytest.mark.asyncio
async def test_supervisor_live_calls_returns_active(
    client, db_session, seeded_assigned_case, agent_auth_headers, supervisor_auth_headers
):
    r = await client.post(
        "/api/v1/calls/dial-start",
        json={"case_id": seeded_assigned_case.id, "device_id": "dev-1"},
        headers=agent_auth_headers,
    )
    assert r.status_code == 201

    resp = await client.get("/api/v1/supervisor/live-calls", headers=supervisor_auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(it["status"] in ("dialing", "live") for it in items)
    assert any(it["call_id"] == r.json()["call_id"] for it in items)


@pytest.mark.asyncio
async def test_supervisor_live_calls_requires_role(client, agent_auth_headers):
    resp = await client.get("/api/v1/supervisor/live-calls", headers=agent_auth_headers)
    assert resp.status_code == 403
