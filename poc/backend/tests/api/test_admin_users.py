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
