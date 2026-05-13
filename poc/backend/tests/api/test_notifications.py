"""Sprint 15.4 — 通知触发器 + 站内信 (PRD §L412)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── Service-level: dispatcher + quota_alerts ─────────────────────


def _seed_admin(db_session, seeded_user, seeded_tenant):
    from app.models.tenant import UserTenantMembership
    db_session.add(UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="admin",
        source_type="INTERNAL",
        is_active=True,
    ))
    db_session.flush()


def test_dispatch_writes_system_notification(db_session, seeded_user, seeded_tenant):
    from app.services.notifications import EventType, dispatch
    from app.models.notification import Notification
    _seed_admin(db_session, seeded_user, seeded_tenant)

    res = dispatch(
        db_session,
        tenant_id=seeded_tenant.id,
        event_type=EventType.QUOTA_WARNING,
        title="测试",
        body="正文",
        recipient_user_ids=[seeded_user.id],
        severity="warn",
        payload={"x": 1},
    )
    assert "system" in res["sent"]
    db_session.commit()
    rows = db_session.query(Notification).filter_by(user_id=seeded_user.id).all()
    assert len(rows) == 1
    assert rows[0].title == "测试" and rows[0].severity == "warn"


def test_dispatch_skipped_when_event_disabled(db_session, seeded_user, seeded_tenant):
    from app.models.notification import Notification
    from app.models.settings import TenantSettings
    from app.services.notifications import EventType, dispatch
    db_session.add(TenantSettings(
        tenant_id=seeded_tenant.id,
        notify_quota_warning=False,  # 关掉
    ))
    db_session.flush()
    res = dispatch(
        db_session,
        tenant_id=seeded_tenant.id,
        event_type=EventType.QUOTA_WARNING,
        title="x", body="x",
        recipient_user_ids=[seeded_user.id],
    )
    assert res["sent"] == []
    assert "event_disabled" in res["skipped"]
    assert db_session.query(Notification).count() == 0


def test_dispatch_routes_to_configured_channels(db_session, seeded_user, seeded_tenant):
    from app.models.settings import TenantSettings
    from app.services.notifications import EventType, dispatch
    db_session.add(TenantSettings(
        tenant_id=seeded_tenant.id,
        notify_channels=["system", "sms", "wechat"],
    ))
    db_session.flush()
    res = dispatch(
        db_session,
        tenant_id=seeded_tenant.id,
        event_type=EventType.QUOTA_WARNING,
        title="x", body="x",
        recipient_user_ids=[seeded_user.id],
    )
    # 全部三个 stub 都成功（log only）
    assert set(res["sent"]) == {"system", "sms", "wechat"}


def test_quota_threshold_crossing_fires_once(db_session, seeded_user, seeded_tenant):
    from app.services.quota_alerts import check_and_notify_quota_thresholds
    _seed_admin(db_session, seeded_user, seeded_tenant)
    seeded_tenant.monthly_minute_quota = 100

    # 跨 80% 阈值（79 → 80）
    fired = check_and_notify_quota_thresholds(
        db_session, tenant=seeded_tenant,
        previous_used=79, current_used=80, quota=100,
    )
    assert 0.80 in fired
    db_session.commit()

    # 同一阈值再次扣分钟（80 → 90）不应再触发
    fired2 = check_and_notify_quota_thresholds(
        db_session, tenant=seeded_tenant,
        previous_used=80, current_used=90, quota=100,
    )
    assert 0.80 not in fired2


def test_quota_threshold_critical_at_100(db_session, seeded_user, seeded_tenant):
    from app.services.quota_alerts import check_and_notify_quota_thresholds
    from app.models.notification import Notification
    _seed_admin(db_session, seeded_user, seeded_tenant)
    seeded_tenant.monthly_minute_quota = 100
    fired = check_and_notify_quota_thresholds(
        db_session, tenant=seeded_tenant,
        previous_used=90, current_used=101, quota=100,
    )
    # 一次性跨过 95% 和 100% 两个阈值
    assert 0.95 in fired
    assert 1.00 in fired
    db_session.commit()
    notifs = db_session.query(Notification).filter_by(user_id=seeded_user.id).all()
    assert any(n.severity == "critical" for n in notifs)


# ── REST API ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_my_notifications_empty(client: AsyncClient, ops_auth_headers):
    resp = await client.get("/api/v1/users/me/notifications", headers=ops_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_unread_count_and_read(
    client: AsyncClient, db_session, seeded_user, seeded_tenant, ops_auth_headers
):
    from app.models.notification import Notification
    db_session.add(Notification(
        tenant_id=seeded_tenant.id,
        user_id=seeded_user.id,
        event_type="quota_warning",
        severity="info",
        title="t1", body="b1",
    ))
    db_session.commit()

    cnt = await client.get(
        "/api/v1/users/me/notifications/unread-count", headers=ops_auth_headers,
    )
    assert cnt.status_code == 200
    assert cnt.json()["unread"] == 1

    listing = await client.get(
        "/api/v1/users/me/notifications", headers=ops_auth_headers,
    )
    nid = listing.json()["items"][0]["id"]

    mark = await client.patch(
        f"/api/v1/users/me/notifications/{nid}/read", headers=ops_auth_headers,
    )
    assert mark.status_code == 204

    cnt2 = await client.get(
        "/api/v1/users/me/notifications/unread-count", headers=ops_auth_headers,
    )
    assert cnt2.json()["unread"] == 0


@pytest.mark.asyncio
async def test_mark_all_read(
    client: AsyncClient, db_session, seeded_user, seeded_tenant, ops_auth_headers
):
    from app.models.notification import Notification
    for i in range(3):
        db_session.add(Notification(
            tenant_id=seeded_tenant.id,
            user_id=seeded_user.id,
            event_type="x", severity="info",
            title=f"t{i}", body="b",
        ))
    db_session.commit()
    resp = await client.patch(
        "/api/v1/users/me/notifications/read-all", headers=ops_auth_headers,
    )
    assert resp.status_code == 204
    cnt = await client.get(
        "/api/v1/users/me/notifications/unread-count", headers=ops_auth_headers,
    )
    assert cnt.json()["unread"] == 0


@pytest.mark.asyncio
async def test_cannot_read_others_notification(
    client: AsyncClient, db_session, seeded_member_user, seeded_tenant, ops_auth_headers
):
    # member_user 的通知，ops_user 不能 mark read（应 404）
    from app.models.notification import Notification
    n = Notification(
        tenant_id=seeded_tenant.id,
        user_id=seeded_member_user.id,
        event_type="x", severity="info",
        title="t", body="b",
    )
    db_session.add(n); db_session.commit()
    resp = await client.patch(
        f"/api/v1/users/me/notifications/{n.id}/read", headers=ops_auth_headers,
    )
    assert resp.status_code == 404


# ── Sprint 15.4b: event_subscribers (script_disabled / case_escalated / wo_completed) ─


def test_notify_script_disabled_writes_to_admin(
    db_session, seeded_user, seeded_tenant, seeded_supervisor_user
):
    """script_disabled 事件应给本租户 admin + supervisor 都发通知。"""
    from app.models.notification import Notification
    from app.models.tenant import UserTenantMembership
    from app.services.notifications.event_subscribers import notify_script_disabled

    _seed_admin(db_session, seeded_user, seeded_tenant)
    db_session.add(UserTenantMembership(
        user_id=seeded_supervisor_user.id,
        tenant_id=seeded_tenant.id,
        role="supervisor",
        source_type="INTERNAL",
        is_active=True,
    ))
    db_session.flush()

    notify_script_disabled(
        db_session,
        tenant_id=seeded_tenant.id,
        script_id=42,
        script_name="测试话术",
    )
    db_session.commit()
    rows = db_session.query(Notification).filter_by(event_type="script_disabled").all()
    user_ids = {r.user_id for r in rows}
    assert seeded_user.id in user_ids
    assert seeded_supervisor_user.id in user_ids


def test_notify_script_disabled_excludes_operator(
    db_session, seeded_user, seeded_tenant
):
    """禁用人不应收到自己触发的通知。"""
    from app.models.notification import Notification
    from app.services.notifications.event_subscribers import notify_script_disabled

    _seed_admin(db_session, seeded_user, seeded_tenant)
    notify_script_disabled(
        db_session,
        tenant_id=seeded_tenant.id,
        script_id=42,
        script_name="测试话术",
        operator_user_id=seeded_user.id,
    )
    db_session.commit()
    cnt = db_session.query(Notification).filter_by(event_type="script_disabled").count()
    assert cnt == 0  # 仅 admin 是 operator 自己


def test_notify_case_escalated(
    db_session, seeded_user, seeded_tenant
):
    from app.models.notification import Notification
    from app.services.notifications.event_subscribers import notify_case_escalated

    _seed_admin(db_session, seeded_user, seeded_tenant)
    notify_case_escalated(
        db_session,
        tenant_id=seeded_tenant.id,
        case_id=123,
        owner_name="张大伟",
        new_stage="escalated",
    )
    db_session.commit()
    rows = db_session.query(Notification).filter_by(event_type="case_escalated").all()
    assert len(rows) == 1
    assert rows[0].severity == "warn"
    assert "升级" in rows[0].title


def test_notify_work_order_completed_falls_back_to_admin(
    db_session, seeded_user, seeded_tenant
):
    from app.models.notification import Notification
    from app.services.notifications.event_subscribers import notify_work_order_completed

    _seed_admin(db_session, seeded_user, seeded_tenant)
    notify_work_order_completed(
        db_session,
        tenant_id=seeded_tenant.id,
        work_order_id=99,
        title="工单测试",
        creator_user_id=None,
    )
    db_session.commit()
    rows = db_session.query(Notification).filter_by(
        event_type="work_order_completed",
    ).all()
    assert len(rows) == 1
    assert rows[0].user_id == seeded_user.id


def test_promise_expiring_scan_finds_due_cases(
    db_session, seeded_tenant, seeded_owner, seeded_member_user
):
    """v1.6 — promise_due_at 字段已建模；扫描应给 assigned_to 发提醒。"""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.models.case import CollectionCase
    from app.models.notification import Notification, NotificationDeliveryLog
    from app.services.notifications.event_subscribers import (
        scan_and_notify_promise_expiring,
    )

    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        assigned_to=seeded_member_user.id,
        pool_type="private",
        stage="promised",
        amount_owed=Decimal("1500.00"),
        promise_due_at=datetime.now(UTC) + timedelta(hours=12),
    )
    db_session.add(case)
    # 不在 24h 内的不该被扫到
    case_far = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        assigned_to=seeded_member_user.id,
        pool_type="private",
        stage="promised",
        amount_owed=Decimal("1500.00"),
        promise_due_at=datetime.now(UTC) + timedelta(days=10),
    )
    db_session.add(case_far)
    db_session.commit()

    fired = scan_and_notify_promise_expiring(db_session)
    db_session.commit()
    assert fired == 1

    notif = (
        db_session.query(Notification)
        .filter_by(event_type="promise_expiring")
        .one()
    )
    assert notif.user_id == seeded_member_user.id

    delivery = (
        db_session.query(NotificationDeliveryLog)
        .filter_by(event_type="promise_expiring", channel="system")
        .one()
    )
    assert delivery.status == "sent"
