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


@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient, ops_auth_headers):
    payload = {
        "name": "新物业公司",
        "admin_phone": "13700137001",
        "plan": "standard",
        "monthly_minute_quota": 500,
    }
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "新物业公司"
    assert data["plan"] == "standard"
    assert data["monthly_minute_quota"] == 500
    assert data["admin_phone_masked"] == "137****7001"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_tenant_invalid_phone(client: AsyncClient, ops_auth_headers):
    payload = {"name": "X公司", "admin_phone": "12345", "plan": "trial"}
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_duplicate_credit_code(
    client: AsyncClient, seeded_tenant, ops_auth_headers, db_session
):
    seeded_tenant.credit_code = "91110000000000001X"
    db_session.flush()

    payload = {
        "name": "另一家公司",
        "admin_phone": "13600136001",
        "plan": "trial",
        "credit_code": "91110000000000001X",
    }
    resp = await client.post("/api/v1/ops/tenants", json=payload, headers=ops_auth_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_CREDIT_CODE"
