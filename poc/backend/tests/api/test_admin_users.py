import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_returns_tenant_members(
    client: AsyncClient,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/users", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert any(u["id"] == seeded_member_user.id for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_requires_admin_role(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/admin/users", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_users_masks_phone(
    client: AsyncClient,
    seeded_tenant,
    seeded_member_user,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/users", headers=admin_auth_headers)
    items = resp.json()["items"]
    member = next(u for u in items if u["id"] == seeded_member_user.id)
    assert "****" in member["phone_masked"]
    assert member["phone_masked"] == "138****8111"


@pytest.mark.asyncio
async def test_create_internal_user(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {
        "name": "督导赵六",
        "phone": "13500135005",
        "password": "Secure@1234",
        "role": "supervisor",
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "督导赵六"
    assert data["role"] == "supervisor"
    assert "****" in data["phone_masked"]


@pytest.mark.asyncio
async def test_create_user_duplicate_phone(
    client: AsyncClient, seeded_tenant, seeded_member_user, admin_auth_headers
):
    payload = {
        "name": "重复手机用户",
        "phone": "13811138111",  # same as seeded_member_user
        "password": "Secure@1234",
        "role": "supervisor",
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_PHONE"


@pytest.mark.asyncio
async def test_create_user_invalid_role(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {
        "name": "超管尝试",
        "phone": "13500135006",
        "password": "Secure@1234",
        "role": "platform_superadmin",  # not in allowed roles
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_invite_link(
    client: AsyncClient, seeded_tenant, admin_auth_headers
):
    payload = {"role": "agent_external", "quota": 30, "expire_days": 7}
    resp = await client.post(
        "/api/v1/admin/users/invite", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert "url" in data
    assert "expires_at" in data
