"""Sprint 11.7 — work order historical query (since/until/room filters)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
def workorder_auth_headers(seeded_user, seeded_tenant, db_session):
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="coordinator",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "coordinator",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


def _make_order(
    db_session, tenant, *, description="电梯故障", days_ago=0, case_id=None,
    order_type="quality", status="open",
):
    from app.models.work import WorkOrder

    wo = WorkOrder(
        tenant_id=tenant.id,
        case_id=case_id,
        order_type=order_type,
        description=description,
        status=status,
    )
    db_session.add(wo)
    db_session.flush()
    if days_ago:
        wo.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        db_session.flush()
    return wo


@pytest.mark.asyncio
async def test_workorders_filter_by_since(
    client: AsyncClient, db_session, seeded_tenant, workorder_auth_headers
):
    _make_order(db_session, seeded_tenant, description="新工单", days_ago=1)
    _make_order(db_session, seeded_tenant, description="旧工单", days_ago=30)

    cutoff = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    resp = await client.get(
        "/api/v1/workorders",
        params={"since": cutoff},
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    descriptions = [w["description"] for w in items]
    assert "新工单" in descriptions
    assert "旧工单" not in descriptions


@pytest.mark.asyncio
async def test_workorders_filter_by_until(
    client: AsyncClient, db_session, seeded_tenant, workorder_auth_headers
):
    _make_order(db_session, seeded_tenant, description="新工单", days_ago=1)
    _make_order(db_session, seeded_tenant, description="旧工单", days_ago=30)

    cutoff = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    resp = await client.get(
        "/api/v1/workorders",
        params={"until": cutoff},
        headers=workorder_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    descriptions = [w["description"] for w in resp.json()["items"]]
    assert "旧工单" in descriptions
    assert "新工单" not in descriptions


@pytest.mark.asyncio
async def test_workorders_filter_by_room(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_owner,
    seeded_case,
    workorder_auth_headers,
):
    """Filtering by owner.room — relies on case → owner join."""
    _make_order(db_session, seeded_tenant, description="案件相关", case_id=seeded_case.id)
    _make_order(db_session, seeded_tenant, description="无案件工单")

    # seeded_owner.room = "101"
    resp = await client.get(
        f"/api/v1/workorders?room={seeded_owner.room}",
        headers=workorder_auth_headers,
    )
    descriptions = [w["description"] for w in resp.json()["items"]]
    assert "案件相关" in descriptions
    assert "无案件工单" not in descriptions


@pytest.mark.asyncio
async def test_workorders_filter_status_closed_for_history(
    client: AsyncClient, db_session, seeded_tenant, workorder_auth_headers
):
    _make_order(db_session, seeded_tenant, description="处理中", status="open")
    _make_order(db_session, seeded_tenant, description="已关闭A", status="closed")
    _make_order(db_session, seeded_tenant, description="已关闭B", status="closed")

    resp = await client.get(
        "/api/v1/workorders?status=closed", headers=workorder_auth_headers
    )
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(i["status"] == "closed" for i in items)
