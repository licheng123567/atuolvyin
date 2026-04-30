import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_cases_creates_owner_and_case(
    client: AsyncClient, admin_auth_headers, seeded_tenant
):
    payload = {
        "rows": [
            {
                "name": "李明",
                "phone": "13800001111",
                "building": "2栋",
                "room": "202",
                "amount_owed": "1500.00",
                "months_overdue": 2,
            }
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped"] == 0
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_import_duplicate_phone_reuses_owner(
    client: AsyncClient, admin_auth_headers, seeded_owner
):
    payload = {
        "rows": [
            {
                "name": seeded_owner.name,
                "phone": "13712345678",  # plaintext phone matching seeded_owner
                "amount_owed": "2000.00",
                "months_overdue": 1,
            }
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["imported"] == 1  # new case created, owner reused


@pytest.mark.asyncio
async def test_import_multiple_rows(
    client: AsyncClient, admin_auth_headers
):
    payload = {
        "rows": [
            {"name": "王五", "phone": "13811110001", "amount_owed": "800.00", "months_overdue": 1},
            {"name": "赵六", "phone": "13811110002", "amount_owed": "1200.00", "months_overdue": 4},
        ]
    }
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["imported"] == 2


@pytest.mark.asyncio
async def test_import_requires_admin_role(client: AsyncClient, ops_auth_headers):
    payload = {"rows": [{"name": "X", "phone": "13800009999"}]}
    resp = await client.post(
        "/api/v1/admin/cases/import", json=payload, headers=ops_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_requires_auth(client: AsyncClient):
    payload = {"rows": [{"name": "X", "phone": "13800009999"}]}
    resp = await client.post("/api/v1/admin/cases/import", json=payload)
    assert resp.status_code == 401
