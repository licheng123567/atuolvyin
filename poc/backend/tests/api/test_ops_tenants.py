import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_tenants_returns_paginated(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get("/api/v1/ops/tenants", headers=ops_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(t["id"] == seeded_tenant.id for t in data["items"])


@pytest.mark.asyncio
async def test_list_tenants_requires_ops_role(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get("/api/v1/ops/tenants", headers=admin_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_tenants_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/ops/tenants")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_tenants_search_by_name(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/tenants",
        params={"q": "测试物业"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["id"] == seeded_tenant.id for t in data["items"])


@pytest.mark.asyncio
async def test_list_tenants_search_no_match(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/tenants",
        params={"q": "绝对不存在的名字xyz"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
