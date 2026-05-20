"""v0.5.4 — 督导对案件的 4 类动作:催回访 / 催办 / 介入处理 / 重新分配。

每动作:
  - 200 OK + 写 AuditLog + 写 Notification(给原催收员;reassign 给新催收员 + 通知原催收员)
  - 在 case_timeline 中可见对应 event_type
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_remind_callback_writes_audit_and_notification(
    client, db_session, seeded_assigned_case, supervisor_auth_headers
):
    from app.models.audit import AuditLog
    from app.models.notification import Notification

    case = seeded_assigned_case
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/remind-callback",
        json={"note": "三天没拨,请联系业主"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "remind_callback"
    assert body["notified_user_id"] == case.assigned_to

    # AuditLog
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.target_type == "case",
            AuditLog.target_id == case.id,
            AuditLog.action == "case.supervisor_remind_callback",
        )
        .one()
    )
    assert audit.payload["note"] == "三天没拨,请联系业主"

    # Notification 给原催收员
    notif = (
        db_session.query(Notification)
        .filter(
            Notification.user_id == case.assigned_to,
            Notification.event_type == "supervisor_action",
        )
        .one()
    )
    assert "催回访" in notif.title


@pytest.mark.asyncio
async def test_urge_writes_audit(
    client, db_session, seeded_assigned_case, supervisor_auth_headers
):
    from app.models.audit import AuditLog

    case = seeded_assigned_case
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/urge",
        json={"note": "已停滞 14 天,请推进"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["action"] == "urge"
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "case.supervisor_urge", AuditLog.target_id == case.id)
        .one()
    )
    assert audit.payload["note"] == "已停滞 14 天,请推进"


@pytest.mark.asyncio
async def test_intervene_requires_note(
    client, db_session, seeded_assigned_case, supervisor_auth_headers
):
    case = seeded_assigned_case
    # 空 note → 422
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/intervene",
        json={"note": ""},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 422
    # 有 note → 200
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/intervene",
        json={"note": "业主投诉,督导接管"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "intervene"


@pytest.mark.asyncio
async def test_reassign_updates_assigned_to(
    client, db_session, seeded_assigned_case, supervisor_auth_headers
):
    """重新分配:案件 assigned_to 切换 + 新催收员收到通知。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.audit import AuditLog
    from app.models.case import CollectionCase
    from app.models.notification import Notification
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    case = seeded_assigned_case
    old_agent_id = case.assigned_to

    # 造一个新催收员
    new_agent = UserAccount(
        phone_enc=encrypt_phone("13811199001"),
        name="新催收员王二",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(new_agent)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=new_agent.id,
            tenant_id=case.tenant_id,
            role="agent",
            work_mode="internal",
            is_active=True,
        )
    )
    db_session.flush()

    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/reassign",
        json={"target_user_id": new_agent.id, "note": "原催收员请假"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "reassign"
    assert body["new_assigned_to"] == new_agent.id

    # case.assigned_to 已切换
    db_session.expire_all()
    case_after = db_session.get(CollectionCase, case.id)
    assert case_after.assigned_to == new_agent.id
    assert case_after.pool_type == "private"

    # AuditLog
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "case.reassigned", AuditLog.target_id == case.id)
        .one()
    )
    assert audit.payload["old_assigned_to"] == old_agent_id
    assert audit.payload["new_assigned_to"] == new_agent.id

    # Notification 给新+原催收员(两条)
    notif_count = (
        db_session.query(Notification)
        .filter(
            Notification.event_type == "supervisor_action",
            Notification.payload["case_id"].astext == str(case.id),
        )
        .count()
    )
    assert notif_count == 2


@pytest.mark.asyncio
async def test_reassign_invalid_target_returns_400(
    client, db_session, seeded_assigned_case, supervisor_auth_headers
):
    case = seeded_assigned_case
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/reassign",
        json={"target_user_id": 99999, "note": "..."},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "ERR_INVALID_TARGET"


@pytest.mark.asyncio
async def test_agent_cannot_use_supervisor_actions(
    client, seeded_assigned_case, agent_auth_headers
):
    case = seeded_assigned_case
    resp = await client.post(
        f"/api/v1/supervisor/cases/{case.id}/urge",
        json={"note": "..."},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_actions_appear_in_case_timeline(
    client, db_session, seeded_assigned_case, supervisor_auth_headers, admin_auth_headers
):
    """督导动作写入后,案件 timeline 应包含对应事件。"""
    case = seeded_assigned_case
    # 催办
    await client.post(
        f"/api/v1/supervisor/cases/{case.id}/urge",
        json={"note": "请推进"},
        headers=supervisor_auth_headers,
    )
    # 拉案件详情看 timeline
    resp = await client.get(
        f"/api/v1/admin/cases/{case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    timeline = resp.json().get("timeline_events", [])
    event_types = [e["type"] for e in timeline]
    assert "case.supervisor_urge" in event_types
    # 找到对应事件验证 note 已加进描述
    urge_event = next(e for e in timeline if e["type"] == "case.supervisor_urge")
    assert "请推进" in urge_event["note"]
