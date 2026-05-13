"""v2.1 Task 2 — self-check 扩展能力字段 + 留痕测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.models.device_capability_log import DeviceCapabilityLog


# ---------- 1. 旧 App 兼容（不传 manufacturer 等）→ post_upload + 默认字段存在
@pytest.mark.asyncio
async def test_legacy_app_no_capability_fields(client, agent_auth_headers):
    """旧 App 自检，向后兼容不破坏。"""
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-test-legacy"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "android-test-legacy",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_call"] is True
    # 字段应该有默认值，不会 KeyError
    assert "recording_capability" in data
    assert "detected_rom" in data
    assert "guidance_text" in data
    # 缺 mfr → aosp_international；缺 android → derive_capability 返回 post_upload
    assert data["recording_capability"] == "post_upload"


# ---------- 2. MIUI 10 (Xiaomi + Android 9) → realtime
@pytest.mark.asyncio
async def test_miui_10_realtime(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-test-miui10"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "android-test-miui10",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "model": "Mi 9",
            "android_version": "9",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_capability"] == "realtime"
    assert "MIUI" in data["detected_rom"]
    assert "实时通话分析已就绪" in data["guidance_text"]


# ---------- 3. Android 14 Pixel → incompatible
@pytest.mark.asyncio
async def test_pixel_14_incompatible(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-test-pixel14"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "android-test-pixel14",
            "recording_dir_ok": True,
            "recording_toggle_on": False,  # Pixel 14 自然没系统录音器
            "permissions_ok": True,
            "manufacturer": "Google",
            "model": "Pixel 8",
            "android_version": "14",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_capability"] == "incompatible"
    assert "AOSP" in data["detected_rom"]
    assert "系统级不支持通话录音" in data["guidance_text"]


# ---------- 4. last_recording_scan_failed=True 强制降级
@pytest.mark.asyncio
async def test_runtime_failure_overrides_matrix(
    client, agent_auth_headers, db_session
):
    """即使矩阵判定 realtime，扫描失败上报后强制 incompatible。"""
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-test-miui-but-failed"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "android-test-miui-but-failed",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "model": "Mi 9",
            "android_version": "9",
            "last_recording_scan_failed": True,  # 关键：实测没找到文件
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_capability"] == "incompatible"
    # 验证 source = runtime_verified
    log = db_session.execute(
        select(DeviceCapabilityLog)
        .where(DeviceCapabilityLog.device_id == "android-test-miui-but-failed")
        .order_by(DeviceCapabilityLog.id.desc())
    ).scalars().first()
    assert log is not None
    assert log.source == "runtime_verified"
    assert log.actual_recording_works is False


# ---------- 5. 写一行 device_capability_log
@pytest.mark.asyncio
async def test_self_check_writes_log_row(client, agent_auth_headers, db_session):
    """每次自检写一行留痕，便于 PC 管理员看历史趋势。"""
    db_session.execute(text("DELETE FROM device_capability_log"))  # 隔离
    db_session.flush()
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-test-log-1"},
        headers=agent_auth_headers,
    )
    await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "android-test-log-1",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "android_version": "10",
        },
        headers=agent_auth_headers,
    )
    rows = db_session.execute(
        select(DeviceCapabilityLog).where(
            DeviceCapabilityLog.device_id == "android-test-log-1"
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].capability == "realtime"
    assert rows[0].source == "static_matrix"
    assert rows[0].actual_recording_works is None


# ---------- 6. admin 看自己租户的所有坐席设备 ----------
@pytest.mark.asyncio
async def test_admin_lists_agent_devices(
    client, db_session, admin_auth_headers, agent_auth_headers
):
    """admin 角色能看到本租户 agent 设备的 latest capability。"""
    db_session.execute(text("DELETE FROM device_capability_log"))
    db_session.flush()
    # agent 先注册 + 自检产生 log
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "android-list-test-1"},
        headers=agent_auth_headers,
    )
    await client.post(
        "/api/v1/devices/self-check",
        headers=agent_auth_headers,
        json={
            "device_id": "android-list-test-1",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "model": "Mi 9",
            "android_version": "9",
        },
    )
    resp = await client.get(
        "/api/v1/admin/agent-devices", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20
    # 至少一行匹配
    assert any(
        item["device_id"] == "android-list-test-1" for item in data["items"]
    )
    item = next(
        i for i in data["items"] if i["device_id"] == "android-list-test-1"
    )
    assert item["latest_capability"] == "realtime"
    assert item["status_label"] == "实时可用"
    assert item["role"] == "agent_internal"
    assert item["user_name"]  # 非空


# ---------- 7. capability 筛选 ----------
@pytest.mark.asyncio
async def test_admin_filter_by_capability(
    client, db_session, admin_auth_headers, agent_auth_headers
):
    """筛选 capability=incompatible 只返回 incompatible 行。"""
    db_session.execute(text("DELETE FROM device_capability_log"))
    db_session.flush()
    # 一台 incompatible（Pixel 14）
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "incompat-1"},
        headers=agent_auth_headers,
    )
    await client.post(
        "/api/v1/devices/self-check",
        headers=agent_auth_headers,
        json={
            "device_id": "incompat-1",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Google",
            "model": "Pixel 8",
            "android_version": "14",
        },
    )
    # 一台 realtime（Xiaomi Android 10）
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "realtime-1"},
        headers=agent_auth_headers,
    )
    await client.post(
        "/api/v1/devices/self-check",
        headers=agent_auth_headers,
        json={
            "device_id": "realtime-1",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
            "manufacturer": "Xiaomi",
            "model": "Mi 10",
            "android_version": "10",
        },
    )
    resp = await client.get(
        "/api/v1/admin/agent-devices?capability=incompatible",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(i["latest_capability"] == "incompatible" for i in items)
    assert any(i["device_id"] == "incompat-1" for i in items)
    assert not any(i["device_id"] == "realtime-1" for i in items)


# ---------- 8. 非授权角色 403 ----------
@pytest.mark.asyncio
async def test_agent_cannot_list_agent_devices(client, agent_auth_headers):
    """agent_internal 拉这个列表应该被拒（仅 admin/supervisor/superadmin）。"""
    resp = await client.get(
        "/api/v1/admin/agent-devices", headers=agent_auth_headers
    )
    assert resp.status_code == 403
