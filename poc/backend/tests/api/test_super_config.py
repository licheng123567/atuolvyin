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


# ── 短信配置 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sms_config_get_empty(client, super_auth_headers):
    r = await client.get("/api/v1/super/sms-config", headers=super_auth_headers)
    assert r.status_code == 200
    assert r.json() is None


@pytest.mark.asyncio
async def test_sms_config_put_then_get(client, super_auth_headers):
    put = await client.put(
        "/api/v1/super/sms-config",
        json={
            "secret_name": "API",
            "secret_key": "s3cr3t",
            "sign_name": "有证慧催",
            "otp_template_id": "T1001",
            "is_active": True,
        },
        headers=super_auth_headers,
    )
    assert put.status_code == 200
    body = put.json()
    assert body["secret_name"] == "API"
    assert body["sign_name"] == "有证慧催"
    assert body["otp_template_id"] == "T1001"
    assert body["is_active"] is True
    assert body["has_secret_key"] is True
    # 明文 secret_key 绝不回传
    assert "secret_key" not in body
    assert "secret_key_enc" not in body

    got = await client.get("/api/v1/super/sms-config", headers=super_auth_headers)
    assert got.json()["secret_name"] == "API"
    assert "secret_key" not in got.json()
    assert "s3cr3t" not in str(got.json())


@pytest.mark.asyncio
async def test_sms_config_put_upsert_keeps_key_when_omitted(client, super_auth_headers):
    """secret_key 传 null 时不改原 key（has_secret_key 仍 True）。"""
    await client.put(
        "/api/v1/super/sms-config",
        json={"secret_name": "API", "secret_key": "k1", "sign_name": "S",
              "otp_template_id": None, "is_active": False},
        headers=super_auth_headers,
    )
    r = await client.put(
        "/api/v1/super/sms-config",
        json={"secret_name": "API2", "secret_key": None, "sign_name": "S2",
              "otp_template_id": None, "is_active": True},
        headers=super_auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["secret_name"] == "API2"
    assert r.json()["has_secret_key"] is True


@pytest.mark.asyncio
async def test_sms_config_requires_superadmin(client, agent_auth_headers):
    """非超管访问 GET → 403。"""
    r = await client.get("/api/v1/super/sms-config", headers=agent_auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_sms_config_put_requires_superadmin(client, agent_auth_headers):
    """非超管发 PUT → 403。"""
    r = await client.put(
        "/api/v1/super/sms-config",
        json={
            "secret_name": "API",
            "secret_key": "s3cr3t",
            "sign_name": "有证慧催",
            "otp_template_id": None,
            "is_active": False,
        },
        headers=agent_auth_headers,
    )
    assert r.status_code == 403
