"""Sprint 15.3 — 督导一键介入 SUPERVISOR_TAKEOVER (PRD §11.2).

5 项验收：
  1. supervisor 调 POST /supervisor/calls/{id}/takeover → 200 + audit + supervisor_name
  2. 跨租户 → 404 / 已结束通话 → 409 / agent 角色 → 403
  3. agent 调 POST /calls/{id}/takeover-response (accepted=true) → 200 + audit
  4. agent 调 takeover-response (accepted=false) → 200 + audit (rejected)
  5. agent 不能响应别人的 call → 404
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


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


@pytest.mark.asyncio
async def test_supervisor_takeover_request(
    client, db_session, seeded_tenant, seeded_member_user, supervisor_auth_headers
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/takeover",
        json={"reason": "客户激烈，主管接手"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "requested"
    assert body["supervisor_name"]
    # audit 记录
    from app.models.audit import AuditLog
    audit = db_session.query(AuditLog).filter_by(
        action="call.takeover_requested", target_id=call.id
    ).first()
    assert audit is not None


@pytest.mark.asyncio
async def test_takeover_cross_tenant_404(
    client, db_session, seeded_member_user, supervisor_auth_headers
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    from app.models.tenant import Tenant
    other = Tenant(
        name="另一",
        admin_phone_enc=encrypt_phone("13700000099"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other); db_session.flush()
    call = CallRecord(
        tenant_id=other.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="live",
        recording_mode="live",
    )
    db_session.add(call); db_session.commit()
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/takeover",
        json={"reason": "x"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_takeover_already_ended_409(
    client, db_session, seeded_tenant, seeded_member_user, supervisor_auth_headers
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="processed",
        recording_mode="post",
    )
    db_session.add(call); db_session.commit()
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/takeover",
        json={"reason": "x"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_agent_cannot_request_takeover_403(
    client, db_session, seeded_tenant, seeded_member_user, agent_auth_headers
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/supervisor/calls/{call.id}/takeover",
        json={"reason": "x"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_response_accepted(
    client, db_session, seeded_tenant, seeded_member_user, agent_auth_headers
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/calls/{call.id}/takeover-response",
        json={"accepted": True, "note": "好的，您接吧"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] is True
    from app.models.audit import AuditLog
    audit = db_session.query(AuditLog).filter_by(
        action="call.takeover_accepted", target_id=call.id
    ).first()
    assert audit is not None


@pytest.mark.asyncio
async def test_agent_response_rejected(
    client, db_session, seeded_tenant, seeded_member_user, agent_auth_headers
):
    call = _make_live_call(db_session, seeded_tenant, seeded_member_user)
    resp = await client.post(
        f"/api/v1/calls/{call.id}/takeover-response",
        json={"accepted": False, "note": "我自己处理得了"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is False
    from app.models.audit import AuditLog
    audit = db_session.query(AuditLog).filter_by(
        action="call.takeover_rejected", target_id=call.id
    ).first()
    assert audit is not None


@pytest.mark.asyncio
async def test_agent_cannot_respond_others_call_404(
    client, db_session, seeded_tenant, seeded_supervisor_user, agent_auth_headers
):
    # 通话归属另一个用户（supervisor）
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_supervisor_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        status="live",
        recording_mode="live",
    )
    db_session.add(call); db_session.commit()
    resp = await client.post(
        f"/api/v1/calls/{call.id}/takeover-response",
        json={"accepted": True},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
