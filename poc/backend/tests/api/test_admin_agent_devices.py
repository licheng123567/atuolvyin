"""Fix 2 (Gap4) — project_manager 应能读 admin/agent-devices。

物业项目经理 nav 中有「实时通话墙」，该页依赖 admin/agent-devices；
改 ALLOWED_ROLES 前 PM 返回 403，改后应 200。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.crypto import encrypt_phone


def _pm_auth_headers(db_session, tenant_id: int) -> dict:
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13000000008"),
        name="物业项目经理",
        password_hash=get_password_hash("Pm@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role="project_manager",
            provider_id=None,  # 物业侧：provider_id IS NULL
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": "project_manager",
            "scope": f"tenant:{tenant_id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_property_pm_can_list_agent_devices(
    client, db_session, seeded_tenant, agent_auth_headers
):
    """物业 PM GET /api/v1/admin/agent-devices → 200（Fix 2 通过后）。"""
    # 先产生至少一条 device_capability_log，避免空列表掩盖问题
    db_session.execute(text("DELETE FROM device_capability_log"))
    db_session.flush()
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "pm-test-device"},
        headers=agent_auth_headers,
    )
    await client.post(
        "/api/v1/devices/self-check",
        headers=agent_auth_headers,
        json={
            "device_id": "pm-test-device",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "model": "Mi 9",
            "android_version": "9",
        },
    )

    headers = _pm_auth_headers(db_session, seeded_tenant.id)
    resp = await client.get("/api/v1/admin/agent-devices", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_provider_pm_cannot_list_agent_devices(
    client, db_session, seeded_tenant
):
    """服务商 PM（provider_id 非 NULL）不可访问 — require_tenant_roles 断言 provider_id IS NULL。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13099990001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()

    user = UserAccount(
        phone_enc=encrypt_phone("13099990002"),
        name="服务商项目经理",
        password_hash=get_password_hash("Pm@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=seeded_tenant.id,
            role="project_manager",
            provider_id=provider.id,  # 服务商侧：provider_id 非 NULL
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": seeded_tenant.id,
            "role": "project_manager",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/admin/agent-devices", headers=headers)
    # require_tenant_roles 断言 provider_id IS NULL → 服务商 PM 仍应 403
    assert resp.status_code == 403, resp.text
