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
