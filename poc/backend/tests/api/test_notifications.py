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
