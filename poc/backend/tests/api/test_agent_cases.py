import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_sees_public_unassigned_cases(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids  # seeded_case is public + unassigned


@pytest.mark.asyncio
async def test_agent_sees_own_private_cases(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign case to agent
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert seeded_case.id in ids


@pytest.mark.asyncio
async def test_claim_case_from_public_pool(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pool_type"] == "private"
    assert data["assigned_to"] is not None


@pytest.mark.asyncio
async def test_claim_already_claimed_case(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign to agent first
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    # Agent tries to claim an already assigned case
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_ALREADY_CLAIMED"


@pytest.mark.asyncio
async def test_claim_nonexistent_case(client: AsyncClient, agent_auth_headers):
    resp = await client.post(
        "/api/v1/agent/cases/999999/claim", headers=agent_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/agent/cases")
    assert resp.status_code == 401
