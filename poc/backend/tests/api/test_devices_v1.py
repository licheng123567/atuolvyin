import pytest


def _make_other_user(db_session, tenant):
    """Create a real other UserAccount + membership; FK requires real id."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    u = UserAccount(
        phone_enc=encrypt_phone(f"139{int.from_bytes(__import__('os').urandom(4), 'big') % 100000000:08d}"),
        name="另一个坐席",
        password_hash=get_password_hash("Other@1234"),
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=u.id,
            tenant_id=tenant.id,
            role="agent",
            work_mode="internal",
            is_active=True,
        )
    )
    db_session.flush()
    return u


@pytest.mark.asyncio
async def test_register_device_creates_record(client, agent_auth_headers, db_session):
    resp = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-001", "brand": "Xiaomi", "model": "12", "os_version": "Android 13"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["device_id"] == "dev-uuid-001"
    assert "user_id" in data
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_register_device_upserts_on_conflict(client, agent_auth_headers):
    payload = {"device_id": "dev-uuid-upsert", "brand": "Samsung"}
    await client.post("/api/v1/devices/register", json=payload, headers=agent_auth_headers)
    payload2 = {"device_id": "dev-uuid-upsert", "brand": "Huawei"}
    resp = await client.post("/api/v1/devices/register", json=payload2, headers=agent_auth_headers)
    assert resp.status_code == 201
    assert resp.json()["device_id"] == "dev-uuid-upsert"
    assert resp.json()["brand"] == "Huawei"


@pytest.mark.asyncio
async def test_self_check_all_ok_returns_can_call_true(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-check"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-uuid-check",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["can_call"] is True


@pytest.mark.asyncio
async def test_self_check_partial_failure_returns_can_call_false(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-partial"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-uuid-partial",
            "recording_dir_ok": True,
            "recording_toggle_on": False,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["can_call"] is False


@pytest.mark.asyncio
async def test_register_requires_auth(client):
    resp = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "no-auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_with_push_reg_id_persists_field(
    client, agent_auth_headers, db_session
):
    """Sprint 12 — push_reg_id must be persisted to DeviceProfile column."""
    from sqlalchemy import select
    from app.models.device import DeviceProfile

    resp = await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "dev-uuid-push-1",
            "brand": "Xiaomi",
            "push_reg_id": "xiaomi-reg-id-aaa111",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["push_reg_id_set"] is True

    device = db_session.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == "dev-uuid-push-1")
    ).scalar_one()
    assert device.push_reg_id == "xiaomi-reg-id-aaa111"
    assert device.push_provider == "xiaomi"


@pytest.mark.asyncio
async def test_register_without_push_reg_id_preserves_existing(
    client, agent_auth_headers, db_session
):
    """A re-register without push fields must keep the previously stored token."""
    from sqlalchemy import select
    from app.models.device import DeviceProfile

    # First register with push fields
    await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "dev-uuid-push-2",
            "brand": "Xiaomi",
            "push_reg_id": "preserve-me-bbb222",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    # Re-register without push fields (e.g. before MiPush has reissued a token)
    resp = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-push-2", "brand": "Xiaomi", "model": "13"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["push_reg_id_set"] is True  # still set

    device = db_session.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == "dev-uuid-push-2")
    ).scalar_one()
    assert device.push_reg_id == "preserve-me-bbb222"
    assert device.push_provider == "xiaomi"
    assert device.model == "13"  # other fields still update normally


@pytest.mark.asyncio
async def test_register_with_different_push_provider(
    client, agent_auth_headers, db_session
):
    """Switching xiaomi -> huawei should overwrite both columns."""
    from sqlalchemy import select
    from app.models.device import DeviceProfile

    await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "dev-uuid-push-3",
            "push_reg_id": "xm-token",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "dev-uuid-push-3",
            "push_reg_id": "hw-token",
            "push_provider": "huawei",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201

    device = db_session.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == "dev-uuid-push-3")
    ).scalar_one()
    assert device.push_reg_id == "hw-token"
    assert device.push_provider == "huawei"


@pytest.mark.asyncio
async def test_self_check_unregistered_returns_specific_code(
    client, agent_auth_headers
):
    """v1.6 — 未注册设备应返回 ERR_DEVICE_NOT_REGISTERED（区别于"属他人"）。"""
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-never-registered",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_DEVICE_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_self_check_owned_by_other_returns_specific_code(
    client, agent_auth_headers, seeded_tenant, db_session
):
    """device_id 存在但 user_id 不匹配 → ERR_DEVICE_OWNED_BY_OTHER（前端引导改账号）。"""
    from app.models.device import DeviceProfile

    # 先用真实的另一个 user 占住 device_id
    other = _make_other_user(db_session, seeded_tenant)
    db_session.add(
        DeviceProfile(
            device_id="dev-someone-else",
            user_id=other.id,
            tenant_id=seeded_tenant.id,
        )
    )
    db_session.commit()

    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-someone-else",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_DEVICE_OWNED_BY_OTHER"


@pytest.mark.asyncio
async def test_self_check_returns_fail_reasons(client, agent_auth_headers):
    """self-check 失败时应列出哪些项不合格，便于 UI 显示。"""
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-fail-reasons"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-fail-reasons",
            "recording_dir_ok": False,
            "recording_toggle_on": False,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["can_call"] is False
    assert "recording_dir" in body["fail_reasons"]
    assert "recording_toggle" in body["fail_reasons"]
    assert "permissions" not in body["fail_reasons"]


@pytest.mark.asyncio
async def test_self_check_all_ok_returns_empty_fail_reasons(
    client, agent_auth_headers
):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-fr-ok"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-fr-ok",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["can_call"] is True
    assert body["fail_reasons"] == []


@pytest.mark.asyncio
async def test_patch_push_reg_requires_device_exists(client, agent_auth_headers):
    """PATCH /devices/push-reg 不应自动创建 device row（避免 push 回调绕过登录建行）。"""
    resp = await client.patch(
        "/api/v1/devices/push-reg",
        json={
            "device_id": "dev-no-row",
            "push_reg_id": "xm-token-1",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_DEVICE_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_patch_push_reg_updates_existing_device(
    client, agent_auth_headers, db_session
):
    """device 存在 → PATCH 写入 push_reg_id；不影响其他字段。"""
    from sqlalchemy import select
    from app.models.device import DeviceProfile

    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-patch-1", "brand": "Xiaomi", "model": "12"},
        headers=agent_auth_headers,
    )

    resp = await client.patch(
        "/api/v1/devices/push-reg",
        json={
            "device_id": "dev-patch-1",
            "push_reg_id": "xm-fresh",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["push_reg_id_set"] is True

    device = db_session.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == "dev-patch-1")
    ).scalar_one()
    assert device.push_reg_id == "xm-fresh"
    assert device.push_provider == "xiaomi"
    assert device.model == "12"  # 未被覆盖


@pytest.mark.asyncio
async def test_patch_push_reg_rejects_other_user_device(
    client, agent_auth_headers, seeded_tenant, db_session
):
    """device_id 属他人 → 403，避免 push 回调跨账号污染。"""
    from app.models.device import DeviceProfile

    other = _make_other_user(db_session, seeded_tenant)
    db_session.add(
        DeviceProfile(
            device_id="dev-other-patch",
            user_id=other.id,
            tenant_id=seeded_tenant.id,
        )
    )
    db_session.commit()

    resp = await client.patch(
        "/api/v1/devices/push-reg",
        json={
            "device_id": "dev-other-patch",
            "push_reg_id": "xm-token",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_DEVICE_OWNED_BY_OTHER"


@pytest.mark.asyncio
async def test_register_response_includes_push_reg_id_set_flag(
    client, agent_auth_headers
):
    """push_reg_id_set is False when no token stored, True when one is."""
    resp_without = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-flag-no"},
        headers=agent_auth_headers,
    )
    assert resp_without.status_code == 201
    assert resp_without.json()["push_reg_id_set"] is False

    resp_with = await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "dev-uuid-flag-yes",
            "push_reg_id": "some-token",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert resp_with.status_code == 201
    assert resp_with.json()["push_reg_id_set"] is True
