"""Sprint 15 — platform_super audit log endpoint tests."""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_audit_logs_returns_seeded_row(
    client: AsyncClient, seeded_audit_log, super_auth_headers
):
    resp = await client.get("/api/v1/super/audit-logs", headers=super_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    actions = [item["action"] for item in data["items"]]
    assert "tenant.create" in actions


@pytest.mark.asyncio
async def test_list_audit_logs_filter_by_action(
    client: AsyncClient, seeded_audit_log, super_auth_headers, db_session
):
    # Insert a different-action row to ensure filter narrows results
    from app.models.audit import AuditLog
    other = AuditLog(
        actor_user_id=seeded_audit_log.actor_user_id,
        actor_role="superadmin",
        tenant_id=seeded_audit_log.tenant_id,
        action="tenant.disable",
        target_type="tenant",
        target_id=seeded_audit_log.target_id,
        payload={"reason": "test"},
    )
    db_session.add(other)
    db_session.flush()

    resp = await client.get(
        "/api/v1/super/audit-logs",
        params={"action": "tenant.disable"},
        headers=super_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["action"] == "tenant.disable" for item in data["items"])
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_audit_logs_filter_by_since(
    client: AsyncClient, seeded_audit_log, super_auth_headers
):
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.get(
        "/api/v1/super/audit-logs",
        params={"since": future},
        headers=super_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_audit_logs_role_guard(
    client: AsyncClient, seeded_audit_log, ops_auth_headers
):
    resp = await client.get("/api/v1/super/audit-logs", headers=ops_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_logs_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/super/audit-logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tenant_create_emits_audit_log(
    client: AsyncClient, ops_auth_headers, super_auth_headers
):
    """Hook test — POST /ops/tenants must drop a tenant.create audit row."""
    payload = {
        "name": "审计测试公司",
        "admin_phone": "13700137055",
        "plan": "trial",
    }
    create_resp = await client.post(
        "/api/v1/ops/tenants", json=payload, headers=ops_auth_headers
    )
    assert create_resp.status_code == 201
    new_id = create_resp.json()["id"]

    resp = await client.get(
        "/api/v1/super/audit-logs",
        params={"action": "tenant.create"},
        headers=super_auth_headers,
    )
    assert resp.status_code == 200
    rows = resp.json()["items"]
    assert any(r["target_id"] == new_id for r in rows)
