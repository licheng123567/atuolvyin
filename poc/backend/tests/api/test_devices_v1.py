import pytest


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
