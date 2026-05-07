# Sprint 16 — POST /api/v1/calls/{call_id}/intent
from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture
def seeded_agent_call(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=b"x",
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        ended_at=datetime.now(UTC),
        duration_sec=120,
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()
    return call


async def test_call_intent_records_audit_log(
    client, agent_auth_headers, seeded_agent_call, db_session
):
    from app.models.audit import AuditLog
    from sqlalchemy import select

    resp = await client.post(
        f"/api/v1/calls/{seeded_agent_call.id}/intent",
        headers=agent_auth_headers,
        json={"action": "transfer_supervisor", "note": "owner情绪激动"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["call_id"] == seeded_agent_call.id
    assert body["action"] == "transfer_supervisor"
    assert body["status"] == "queued"

    db_session.expire_all()
    log = db_session.execute(
        select(AuditLog).where(AuditLog.target_id == seeded_agent_call.id)
    ).scalar_one()
    assert log.action == "call.intent.transfer_supervisor"
    assert log.payload == {"note": "owner情绪激动"}


async def test_call_intent_rejects_unknown_action(
    client, agent_auth_headers, seeded_agent_call
):
    resp = await client.post(
        f"/api/v1/calls/{seeded_agent_call.id}/intent",
        headers=agent_auth_headers,
        json={"action": "delete_call"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_INVALID_INTENT"


async def test_call_intent_rejects_other_user_call(
    client, agent_auth_headers, db_session, seeded_tenant, seeded_case
):
    """Another agent's call must not accept intent from this agent."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.call import CallRecord
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    other = UserAccount(
        phone_enc=encrypt_phone("13900000099"),
        name="另一个坐席",
        password_hash=get_password_hash("X@1234"),
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=other.id,
            tenant_id=seeded_tenant.id,
            role="agent_internal",
            source_type="INTERNAL",
            is_active=True,
        )
    )
    db_session.flush()

    other_call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=other.id,
        callee_phone_enc=b"x",
        started_at=datetime.now(UTC),
        duration_sec=10,
        status="uploaded",
    )
    db_session.add(other_call)
    db_session.flush()

    resp = await client.post(
        f"/api/v1/calls/{other_call.id}/intent",
        headers=agent_auth_headers,
        json={"action": "send_payment_code"},
    )
    assert resp.status_code == 403


async def test_case_intent_records_audit_log(
    client, agent_auth_headers, seeded_case, db_session
):
    from app.models.audit import AuditLog
    from sqlalchemy import select

    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/intent",
        headers=agent_auth_headers,
        json={"action": "transfer_legal", "note": "建议升级至法务"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == seeded_case.id
    assert body["action"] == "transfer_legal"

    db_session.expire_all()
    log = db_session.execute(
        select(AuditLog).where(AuditLog.target_id == seeded_case.id)
    ).scalar_one()
    assert log.action == "case.intent.transfer_legal"


async def test_case_intent_rejects_unknown_action(
    client, agent_auth_headers, seeded_case
):
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/intent",
        headers=agent_auth_headers,
        json={"action": "delete_case"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_INVALID_INTENT"
