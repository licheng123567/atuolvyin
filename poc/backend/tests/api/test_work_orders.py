"""Sprint 13 — Work Order endpoints tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_work_order(db_session, seeded_tenant, seeded_case):
    from app.models.work import WorkOrder

    wo = WorkOrder(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        order_type="quality",
        description="物业服务质量投诉",
        status="open",
    )
    db_session.add(wo)
    db_session.flush()
    return wo


@pytest.fixture
def workorder_auth_headers(db_session, seeded_user, seeded_tenant):
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="workorder",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "workorder",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


# ── List ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_work_orders_returns_seeded(
    client: AsyncClient, seeded_work_order, workorder_auth_headers
):
    resp = await client.get("/api/v1/workorders", headers=workorder_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(i["id"] == seeded_work_order.id for i in data["items"])


@pytest.mark.asyncio
async def test_list_work_orders_filter_by_status(
    client: AsyncClient,
    seeded_work_order,
    workorder_auth_headers,
    db_session,
    seeded_tenant,
):
    from app.models.work import WorkOrder

    closed_one = WorkOrder(
        tenant_id=seeded_tenant.id,
        order_type="dispute",
        description="已解决工单",
        status="closed",
    )
    db_session.add(closed_one)
    db_session.flush()

    resp = await client.get(
        "/api/v1/workorders",
        params={"status": "open"},
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["status"] == "open" for i in items)
    assert any(i["id"] == seeded_work_order.id for i in items)
    assert all(i["id"] != closed_one.id for i in items)


# ── Detail ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_work_order_detail_includes_case(
    client: AsyncClient, seeded_work_order, workorder_auth_headers
):
    resp = await client.get(
        f"/api/v1/workorders/{seeded_work_order.id}",
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_work_order.id
    assert data["case"] is not None
    assert data["case"]["owner_name"] == "张三"


# ── Create ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_work_order(
    client: AsyncClient, seeded_case, workorder_auth_headers
):
    resp = await client.post(
        "/api/v1/workorders",
        json={
            "order_type": "reduction",
            "description": "申请减免物业费",
            "case_id": seeded_case.id,
        },
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["order_type"] == "reduction"
    assert data["status"] == "open"
    assert data["case_id"] == seeded_case.id


# ── Patch ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_work_order_updates_status_and_assignee(
    client: AsyncClient,
    seeded_work_order,
    workorder_auth_headers,
    seeded_member_user,
):
    resp = await client.patch(
        f"/api/v1/workorders/{seeded_work_order.id}",
        json={
            "status": "in_progress",
            "assigned_to": seeded_member_user.id,
            "resolution": "正在处理中",
        },
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["assigned_to"] == seeded_member_user.id
    assert data["assignee_name"] == seeded_member_user.name


# ── Role guard ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_work_orders_reject_unauthorized_role(
    client: AsyncClient, seeded_work_order, agent_auth_headers
):
    resp = await client.get(
        "/api/v1/workorders", headers=agent_auth_headers
    )
    assert resp.status_code == 403
