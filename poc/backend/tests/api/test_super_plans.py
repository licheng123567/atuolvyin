"""Sprint 15 — PlanConfig CRUD tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_plans_returns_seeded(
    client: AsyncClient, seeded_plan_config, super_auth_headers
):
    resp = await client.get("/api/v1/super/plans", headers=super_auth_headers)
    assert resp.status_code == 200
    plan_names = [p["plan_name"] for p in resp.json()]
    assert "trial" in plan_names
    assert "basic" in plan_names


@pytest.mark.asyncio
async def test_create_plan_success(client: AsyncClient, super_auth_headers):
    body = {
        "plan_name": "premium",
        "display_name": "高级版",
        "monthly_minutes": 5000,
        "price_monthly": 599,
        "features": {"realtime_assist": True, "audit_export": True},
        "is_active": True,
    }
    resp = await client.post(
        "/api/v1/super/plans", json=body, headers=super_auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["plan_name"] == "premium"
    assert data["monthly_minutes"] == 5000
    assert data["features"]["audit_export"] is True


@pytest.mark.asyncio
async def test_create_plan_duplicate_name_409(
    client: AsyncClient, seeded_plan_config, super_auth_headers
):
    body = {
        "plan_name": "trial",  # already seeded
        "display_name": "重复试用",
        "monthly_minutes": 60,
        "price_monthly": 0,
        "features": {},
    }
    resp = await client.post(
        "/api/v1/super/plans", json=body, headers=super_auth_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_DUPLICATE_PLAN_NAME"


@pytest.mark.asyncio
async def test_patch_plan_updates_fields(
    client: AsyncClient, seeded_plan_config, super_auth_headers
):
    plan_id = seeded_plan_config[1].id  # basic
    resp = await client.patch(
        f"/api/v1/super/plans/{plan_id}",
        json={"display_name": "基础版（升级）", "monthly_minutes": 800},
        headers=super_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "基础版（升级）"
    assert data["monthly_minutes"] == 800


@pytest.mark.asyncio
async def test_toggle_plan_active(
    client: AsyncClient, seeded_plan_config, super_auth_headers
):
    plan_id = seeded_plan_config[0].id
    resp = await client.patch(
        f"/api/v1/super/plans/{plan_id}/active",
        json={"is_active": False},
        headers=super_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_plans_role_guard(
    client: AsyncClient, seeded_plan_config, ops_auth_headers
):
    resp = await client.get("/api/v1/super/plans", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_plans_superadmin_role_allowed(
    client: AsyncClient, seeded_plan_config, superadmin_auth_headers
):
    resp = await client.get("/api/v1/super/plans", headers=superadmin_auth_headers)
    assert resp.status_code == 200
