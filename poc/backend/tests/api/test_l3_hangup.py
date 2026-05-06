"""Sprint 15.2 — L3 自动挂断 + 督导手动 force-hangup (PRD §13).

5 项验收：
  1. is_l3_hangup_enabled 默认 False / TenantSettings 改 True 后返回 True
  2. maybe_auto_hangup_for_l3：L3 + 设置开启 → dispatch；L3 + 设置关闭 → 不 dispatch
  3. POST /supervisor/calls/{id}/force-hangup 由 supervisor 调用 → 200 + audit log + supervisor 房间收到
  4. 同接口 跨租户 → 404；通话已结束 → 409
  5. agent 角色不能调 force-hangup → 403
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _make_live_call(db_session, tenant, member_user):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="live",
        recording_mode="live",
        started_at=datetime.now(UTC) - timedelta(minutes=2),
        last_heartbeat_at=datetime.now(UTC),
    )
    db_session.add(call); db_session.commit()
    return call


# ── 1. settings 开关 ────────────────────────────────────────────


def test_is_l3_hangup_enabled_default_false(db_session, seeded_tenant):
    from app.services.call_intervention import is_l3_hangup_enabled
    assert is_l3_hangup_enabled(db_session, seeded_tenant.id) is False


def test_is_l3_hangup_enabled_true_when_set(db_session, seeded_tenant):
    from app.models.settings import TenantSettings
    from app.services.call_intervention import is_l3_hangup_enabled
    db_session.add(TenantSettings(
        tenant_id=seeded_tenant.id,
        l3_hangup_enabled=True,
    ))
    db_session.commit()
    assert is_l3_hangup_enabled(db_session, seeded_tenant.id) is True


# ── 2. maybe_auto_hangup_for_l3 ────────────────────────────────


@pytest.mark.asyncio
async def test_l3_event_triggers_hangup_when_enabled(
    db_session, seeded_tenant, seeded_member_user
):
    from app.models.settings import TenantSettings
    from app.services.call_intervention import maybe_auto_hangup_for_l3
    db_session.add(TenantSettings(tenant_id=seeded_tenant.id, l3_hangup_enabled=True))
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)

    fired = await maybe_auto_hangup_for_l3(
        db_session,
        call_id=call.id,
        risk_event={
            "level": "L3",
            "category": "agent_violation",
            "matched_keywords": ["威胁"],
        },
    )
    assert fired is True


@pytest.mark.asyncio
async def test_l3_event_skipped_when_disabled(
    db_session, seeded_tenant, seeded_member_user
):
    from app.services.call_intervention import maybe_auto_hangup_for_l3
    # 不创建 TenantSettings → 默认 False
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    fired = await maybe_auto_hangup_for_l3(
        db_session,
        call_id=call.id,
        risk_event={"level": "L3", "category": "agent_violation"},
    )
    assert fired is False


@pytest.mark.asyncio
async def test_non_l3_event_never_hangs_up(
    db_session, seeded_tenant, seeded_member_user
):
    from app.models.settings import TenantSettings
    from app.services.call_intervention import maybe_auto_hangup_for_l3
    db_session.add(TenantSettings(tenant_id=seeded_tenant.id, l3_hangup_enabled=True))
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    fired = await maybe_auto_hangup_for_l3(
        db_session,
        call_id=call.id,
        risk_event={"level": "L2", "category": "owner_threat"},
    )
    assert fired is False


# ── 3. supervisor manual force-hangup endpoint ─────────────────


@pytest.mark.asyncio
async def test_supervisor_force_hangup_success(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    supervisor_auth_headers,
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/force-hangup",
        json={"reason": "客户激烈投诉，主管介入"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["call_id"] == call.id
    assert body["triggered_by"] == "supervisor.manual"

    # audit log 应该写入
    from app.models.audit import AuditLog
    audit = db_session.query(AuditLog).filter_by(
        action="call.force_hangup", target_id=call.id,
    ).first()
    assert audit is not None
    assert audit.payload["triggered_by"] == "supervisor.manual"


@pytest.mark.asyncio
async def test_supervisor_force_hangup_cross_tenant_404(
    client, db_session, seeded_member_user, supervisor_auth_headers
):
    # 另起一个租户 + 通话
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant
    from app.models.call import CallRecord
    other_tenant = Tenant(
        name="另一租户",
        admin_phone_enc=encrypt_phone("13700000099"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other_tenant); db_session.flush()
    call = CallRecord(
        tenant_id=other_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="live",
        recording_mode="live",
    )
    db_session.add(call); db_session.commit()

    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/force-hangup",
        json={"reason": "x"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_supervisor_force_hangup_already_ended_409(
    client, db_session, seeded_tenant, seeded_member_user, supervisor_auth_headers
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="processed",  # 已结束
        recording_mode="post",
    )
    db_session.add(call); db_session.commit()
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/force-hangup",
        json={"reason": "x"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_agent_role_cannot_force_hangup(
    client, db_session, seeded_tenant, seeded_member_user, agent_auth_headers
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/force-hangup",
        json={"reason": "x"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
