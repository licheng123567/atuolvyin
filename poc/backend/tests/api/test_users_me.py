import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.fixture
def ops_headers(client, seeded_user):
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": None,
        "role": "platform_ops",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_me_returns_identity(client: AsyncClient, seeded_user, ops_headers):
    resp = await client.get("/api/v1/users/me", headers=ops_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_user.id
    assert data["name"] == seeded_user.name
    assert data["role"] == "platform_ops"
    assert data["tenant_id"] is None
    assert data["scope"] == "platform"


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert resp.status_code == 401
