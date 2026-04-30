import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_assign_cases_updates_assigned_to(
    client: AsyncClient,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_count"] == 1


@pytest.mark.asyncio
async def test_assign_cases_user_not_in_tenant(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": 999999},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_USER_NOT_IN_TENANT"


@pytest.mark.asyncio
async def test_assign_ignores_case_ids_from_other_tenant(
    client: AsyncClient,
    admin_auth_headers,
    seeded_member_user,
):
    resp = await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [999998, 999999], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_update_stage_changes_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.patch(
        f"/api/v1/admin/cases/{seeded_case.id}/stage",
        json={"stage": "in_progress"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "in_progress"


@pytest.mark.asyncio
async def test_update_stage_rejects_invalid_stage(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.patch(
        f"/api/v1/admin/cases/{seeded_case.id}/stage",
        json={"stage": "invalid_stage"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_stage_not_found(client: AsyncClient, admin_auth_headers):
    resp = await client.patch(
        "/api/v1/admin/cases/999999/stage",
        json={"stage": "paid"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
