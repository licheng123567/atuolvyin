"""Sprint 14.1 — 实时 vs 事后计费分离 (PRD §20.1.1).

5 项验收：
  1. CallRecord.recording_mode 默认 'post'
  2. /upload 累计到 used_minutes + post_minutes（不动 realtime_minutes）
  3. PlanConfig 双配额字段可读写
  4. admin/dashboard/stats 返回 realtime_min / post_min / realtime_quota / post_quota
  5. super/cost/dashboard 返回 total_realtime_this_month / total_post_this_month + 行级 realtime/post_minutes
"""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


# ── 1. recording_mode 默认值 ─────────────────────────────────────


def test_call_record_recording_mode_default(db_session, seeded_tenant, seeded_member_user):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
    )
    db_session.add(call)
    db_session.flush()
    assert call.recording_mode == "post"


def test_call_record_recording_mode_invalid_rejected(
    db_session, seeded_tenant, seeded_member_user
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        initiated_by="app",
        recording_mode="bogus",
    )
    db_session.add(call)
    with pytest.raises(Exception):  # noqa: B017 — IntegrityError, but vendor-agnostic
        db_session.flush()
    db_session.rollback()


# ── 2. PlanConfig 双配额字段 ─────────────────────────────────────


def test_plan_config_dual_quota_fields(db_session):
    from app.models.audit import PlanConfig

    plan = PlanConfig(
        plan_name="t14_test",
        display_name="14测试套餐",
        monthly_minutes=1000,
        monthly_realtime_minutes=200,
        monthly_post_minutes=800,
    )
    db_session.add(plan)
    db_session.flush()
    db_session.refresh(plan)
    assert plan.monthly_realtime_minutes == 200
    assert plan.monthly_post_minutes == 800


# ── 3. /upload 累计 used + post（不动 realtime）─────────────────


@pytest.mark.asyncio
async def test_upload_accumulates_post_minutes_only(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_member_user,
    agent_auth_headers,
):
    from app.models.case import CollectionCase, OwnerProfile
    from app.models.device import DeviceProfile
    from app.models.tenant import TenantMinuteUsage
    from app.core.crypto import encrypt_phone
    from datetime import datetime, UTC, timedelta

    seeded_tenant.monthly_minute_quota = 1000
    db_session.add(DeviceProfile(
        device_id="dev-billing-1",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        brand="Xiaomi", model="13", os_version="14",
    ))
    owner = OwnerProfile(
        tenant_id=seeded_tenant.id,
        name="测试业主",
        phone_enc=encrypt_phone("13800000099"),
    )
    db_session.add(owner); db_session.flush()
    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=owner.id,
        stage="new",
        assigned_to=seeded_member_user.id,
    )
    db_session.add(case); db_session.flush()
    db_session.commit()

    started = datetime.now(UTC) - timedelta(minutes=2)
    ended = datetime.now(UTC)
    files = {
        "file": ("test.mp3", io.BytesIO(b"x" * 200), "audio/mpeg"),
    }
    data = {
        "device_id": "dev-billing-1",
        "case_id": str(case.id),
        "callee_phone": "13800000099",
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_sec": "120",  # 2 分钟
    }
    resp = await client.post(
        "/api/v1/calls/upload",
        files=files,
        data=data,
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text

    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.expire_all()
    usage = db_session.query(TenantMinuteUsage).filter_by(
        tenant_id=seeded_tenant.id, year_month=ym
    ).one()
    assert usage.used_minutes == 2
    assert usage.post_minutes == 2
    assert usage.realtime_minutes == 0  # upload path 不动 realtime


# ── 4. admin dashboard 返回拆分字段 ──────────────────────────────


@pytest.mark.asyncio
async def test_admin_dashboard_returns_split_quota(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    admin_auth_headers,
):
    from app.models.audit import PlanConfig
    from app.models.tenant import TenantMinuteUsage
    from datetime import datetime, UTC

    seeded_tenant.plan = "t14_dashboard"
    seeded_tenant.monthly_minute_quota = 1000
    db_session.add(PlanConfig(
        plan_name="t14_dashboard",
        display_name="14面板套餐",
        monthly_minutes=1000,
        monthly_realtime_minutes=300,
        monthly_post_minutes=700,
    ))
    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.add(TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month=ym,
        used_minutes=15,
        realtime_minutes=5,
        post_minutes=10,
    ))
    db_session.commit()

    resp = await client.get(
        "/api/v1/admin/dashboard/stats", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    quota = body["minute_quota"]
    assert quota["used_min"] == 15
    assert quota["realtime_min"] == 5
    assert quota["post_min"] == 10
    assert quota["realtime_quota"] == 300
    assert quota["post_quota"] == 700


# ── 5. super cost dashboard 返回拆分字段 ────────────────────────


@pytest.mark.asyncio
async def test_super_cost_dashboard_returns_split(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    superadmin_auth_headers,
):
    from app.models.tenant import TenantMinuteUsage
    from datetime import datetime, UTC

    seeded_tenant.monthly_minute_quota = 600
    ym = datetime.now(UTC).strftime("%Y-%m")
    db_session.add(TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month=ym,
        used_minutes=42,
        realtime_minutes=18,
        post_minutes=24,
    ))
    db_session.commit()

    resp = await client.get(
        "/api/v1/super/cost/dashboard", headers=superadmin_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_used_this_month"] == 42
    assert body["total_realtime_this_month"] == 18
    assert body["total_post_this_month"] == 24
    # 行级
    target = next(r for r in body["tenant_ranking"] if r["tenant_id"] == seeded_tenant.id)
    assert target["realtime_minutes"] == 18
    assert target["post_minutes"] == 24
