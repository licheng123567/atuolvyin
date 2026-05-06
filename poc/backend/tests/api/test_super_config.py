"""Sprint 10 — super_config tests (LLM prompts + blockchain config)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── L1969 LLM prompt management ─────────────────────────────────────


@pytest.mark.asyncio
async def test_create_prompt_auto_versions(
    client: AsyncClient, super_auth_headers
):
    p1 = await client.post(
        "/api/v1/super/llm-prompts",
        json={"name": "intent_classifier", "body": "v1 body"},
        headers=super_auth_headers,
    )
    assert p1.status_code == 201
    assert p1.json()["version"] == 1

    p2 = await client.post(
        "/api/v1/super/llm-prompts",
        json={"name": "intent_classifier", "body": "v2 body"},
        headers=super_auth_headers,
    )
    assert p2.status_code == 201
    assert p2.json()["version"] == 2


@pytest.mark.asyncio
async def test_activate_prompt_deactivates_siblings(
    client: AsyncClient, super_auth_headers
):
    p1 = await client.post(
        "/api/v1/super/llm-prompts",
        json={"name": "p", "body": "v1"},
        headers=super_auth_headers,
    )
    p2 = await client.post(
        "/api/v1/super/llm-prompts",
        json={"name": "p", "body": "v2"},
        headers=super_auth_headers,
    )
    p1_id, p2_id = p1.json()["id"], p2.json()["id"]

    a1 = await client.patch(
        f"/api/v1/super/llm-prompts/{p1_id}/active",
        json={"is_active": True},
        headers=super_auth_headers,
    )
    assert a1.json()["is_active"] is True

    a2 = await client.patch(
        f"/api/v1/super/llm-prompts/{p2_id}/active",
        json={"is_active": True},
        headers=super_auth_headers,
    )
    assert a2.json()["is_active"] is True

    listing = await client.get(
        "/api/v1/super/llm-prompts", headers=super_auth_headers
    )
    by_id = {r["id"]: r for r in listing.json()}
    assert by_id[p1_id]["is_active"] is False
    assert by_id[p2_id]["is_active"] is True


@pytest.mark.asyncio
async def test_activate_unknown_prompt_404(
    client: AsyncClient, super_auth_headers
):
    resp = await client.patch(
        "/api/v1/super/llm-prompts/999999/active",
        json={"is_active": True},
        headers=super_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_llm_prompts_require_super(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/super/llm-prompts", headers=ops_auth_headers)
    assert resp.status_code == 403


# ── L1972 blockchain config ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_blockchain_config_initial_null(
    client: AsyncClient, super_auth_headers
):
    resp = await client.get(
        "/api/v1/super/blockchain-config", headers=super_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_blockchain_config_put_then_get(
    client: AsyncClient, super_auth_headers
):
    body = {
        "provider": "antchain",
        "api_endpoint": "https://api.antchain.example/attest",
        "api_key": "secret-key-001",
        "is_active": True,
    }
    put = await client.put(
        "/api/v1/super/blockchain-config", json=body, headers=super_auth_headers
    )
    assert put.status_code == 200
    data = put.json()
    assert data["provider"] == "antchain"
    assert data["has_api_key"] is True
    # Never echo the raw key
    assert "api_key" not in data
    assert "secret-key-001" not in str(data)

    get = await client.get(
        "/api/v1/super/blockchain-config", headers=super_auth_headers
    )
    assert get.json()["api_endpoint"].endswith("/attest")


@pytest.mark.asyncio
async def test_blockchain_config_put_invalid_provider(
    client: AsyncClient, super_auth_headers
):
    resp = await client.put(
        "/api/v1/super/blockchain-config",
        json={
            "provider": "evilchain",
            "api_endpoint": "https://x",
        },
        headers=super_auth_headers,
    )
    assert resp.status_code == 422
