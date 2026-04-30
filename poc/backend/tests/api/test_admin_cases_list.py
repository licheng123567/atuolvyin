import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_cases_returns_seeded(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get("/api/v1/admin/cases", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_list_cases_filters_by_pool_type(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/admin/cases?pool_type=public", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["pool_type"] == "public"


@pytest.mark.asyncio
async def test_list_cases_filters_by_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/admin/cases?stage=new", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["stage"] == "new"


@pytest.mark.asyncio
async def test_list_cases_keyword_filter(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/admin/cases?keyword={seeded_owner.name}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_cases_includes_owner_info(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get("/api/v1/admin/cases", headers=admin_auth_headers)
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == seeded_case.id)
    assert item["owner"]["name"] == seeded_owner.name
    assert "****" in item["owner"]["phone_masked"]


@pytest.mark.asyncio
async def test_get_case_detail(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_case.id
    assert data["owner"]["name"] == seeded_owner.name


@pytest.mark.asyncio
async def test_get_case_detail_not_found(client: AsyncClient, admin_auth_headers):
    resp = await client.get("/api/v1/admin/cases/999999", headers=admin_auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/cases")
    assert resp.status_code == 401
