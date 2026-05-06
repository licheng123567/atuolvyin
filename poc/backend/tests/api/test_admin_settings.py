"""Sprint 8.5 — admin tenant settings tests (PRD §3.14)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_settings_returns_defaults_when_unset(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get("/api/v1/admin/settings", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "recording_mode": "auto",
        "l3_hangup_enabled": False,
        "contact_freq_max": 3,
        "retention_days": 365,
        "notify_quota_warning": True,
        "notify_script_disabled": True,
        "notify_work_order_completed": True,
        "notify_case_escalated": True,
        "notify_promise_expiring": True,
        "notify_channels": ["system"],
    }


@pytest.mark.asyncio
async def test_patch_settings_updates_and_persists(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "recording_mode": "live",
            "l3_hangup_enabled": True,
            "contact_freq_max": 5,
            "retention_days": 730,
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["recording_mode"] == "live"
    assert resp.json()["l3_hangup_enabled"] is True

    # Re-fetch should return the updated values
    resp2 = await client.get("/api/v1/admin/settings", headers=admin_auth_headers)
    assert resp2.json()["recording_mode"] == "live"
    assert resp2.json()["contact_freq_max"] == 5
    assert resp2.json()["retention_days"] == 730


@pytest.mark.asyncio
async def test_patch_settings_partial_update(
    client: AsyncClient, admin_auth_headers
):
    # Set initial state
    await client.patch(
        "/api/v1/admin/settings",
        json={"recording_mode": "post"},
        headers=admin_auth_headers,
    )
    # Partial update only flips one flag
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"l3_hangup_enabled": True},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recording_mode"] == "post"
    assert data["l3_hangup_enabled"] is True


@pytest.mark.asyncio
async def test_patch_settings_validates_recording_mode(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"recording_mode": "weird"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_settings_validates_freq_range(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"contact_freq_max": 0},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_settings_validates_retention_min(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"retention_days": 7},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_settings_requires_admin(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get("/api/v1/admin/settings", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_settings_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/settings")
    assert resp.status_code == 401


# Sprint 12.3 — 通知规则（PRD §L412）


@pytest.mark.asyncio
async def test_patch_notification_flags(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={
            "notify_quota_warning": False,
            "notify_promise_expiring": False,
            "notify_channels": ["system", "sms"],
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notify_quota_warning"] is False
    assert data["notify_promise_expiring"] is False
    # untouched flags retain default
    assert data["notify_script_disabled"] is True
    assert data["notify_case_escalated"] is True
    assert data["notify_work_order_completed"] is True
    assert data["notify_channels"] == ["system", "sms"]


@pytest.mark.asyncio
async def test_patch_notification_channels_rejects_unknown(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"notify_channels": ["system", "fax"]},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_notification_persists(
    client: AsyncClient, admin_auth_headers
):
    await client.patch(
        "/api/v1/admin/settings",
        json={"notify_channels": ["sms"], "notify_case_escalated": False},
        headers=admin_auth_headers,
    )
    resp = await client.get("/api/v1/admin/settings", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["notify_channels"] == ["sms"]
    assert data["notify_case_escalated"] is False
