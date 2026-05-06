"""Sprint 14.3 — user preferences endpoint (PRD §8.2)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_returns_empty_dict_by_default(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/users/me/preferences", headers=ops_auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"preferences": {}}


@pytest.mark.asyncio
async def test_patch_merges_into_preferences(
    client: AsyncClient, db_session, seeded_user, ops_auth_headers
):
    r1 = await client.patch(
        "/api/v1/users/me/preferences",
        json={"preferences": {"app_intro_dismissed": True}},
        headers=ops_auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["preferences"]["app_intro_dismissed"] is True

    # 第二次 patch 应该 merge 不覆盖
    r2 = await client.patch(
        "/api/v1/users/me/preferences",
        json={"preferences": {"theme": "dark"}},
        headers=ops_auth_headers,
    )
    assert r2.status_code == 200
    prefs = r2.json()["preferences"]
    assert prefs["app_intro_dismissed"] is True
    assert prefs["theme"] == "dark"


@pytest.mark.asyncio
async def test_unauthenticated_blocked(client: AsyncClient):
    resp = await client.get("/api/v1/users/me/preferences")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_app_info_public_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/public/app-info")
    assert resp.status_code == 200
    body = resp.json()
    assert "apk_url" in body and body["apk_url"].startswith("http")
    assert "apk_version" in body
    assert "min_android_version" in body
    assert "notes" in body
