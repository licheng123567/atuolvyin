import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_supervisor_can_see_all_tenant_cases(
    client: AsyncClient, supervisor_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_supervisor_cases_include_owner_info(
    client: AsyncClient, supervisor_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=supervisor_auth_headers
    )
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == seeded_case.id)
    assert item["owner"]["name"] == seeded_owner.name
    # v1.7.0 — supervisor 是物业内部角色，phone_masked 字段返回明文
    assert len(item["owner"]["phone_masked"]) == 11
    assert item["owner"]["phone_masked"].startswith("1")


@pytest.mark.asyncio
async def test_supervisor_filter_by_assigned_to(
    client: AsyncClient,
    supervisor_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # First assign the case
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    resp = await client.get(
        f"/api/v1/supervisor/cases?assigned_to={seeded_member_user.id}",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["assigned_to"] == seeded_member_user.id


@pytest.mark.asyncio
async def test_supervisor_requires_supervisor_role(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/supervisor/cases", headers=admin_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_cases_pagination(
    client: AsyncClient, supervisor_auth_headers, seeded_case
):
    resp = await client.get(
        "/api/v1/supervisor/cases?page=1&page_size=5",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert len(data["items"]) <= 5
