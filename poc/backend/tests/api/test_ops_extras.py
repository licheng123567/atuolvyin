"""Sprint 10 — ops_extras tests (settlements / followups / announcements / my-audit)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── L1999 settlements overview ──────────────────────────────────────


@pytest.fixture
def seeded_full_settlement(db_session, seeded_tenant):
    from app.core.crypto import encrypt_phone
    from app.models.settlement import SettlementStatement
    from app.models.tenant import ProviderTenantContract, ServiceProvider

    p = ServiceProvider(
        name="结算 SP",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900099001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()

    contract = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=p.id,
        signed_at=datetime.now(UTC),
        service_types=["collection"],
        status="active",
    )
    db_session.add(contract)
    db_session.flush()

    s = SettlementStatement(
        contract_id=contract.id,
        period_start=datetime(2026, 3, 1, tzinfo=UTC),
        period_end=datetime(2026, 4, 1, tzinfo=UTC),
        total_amount=Decimal("8000.00"),
        status="DRAFT",
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.mark.asyncio
async def test_settlements_overview_aggregates_pending_and_overdue(
    client: AsyncClient, seeded_full_settlement, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/settlements/overview", headers=ops_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["total_pending"]) >= Decimal("8000.00")
    assert data["overdue_count"] >= 1
    assert any(i["tenant_name"] == "测试物业公司" for i in data["items"])


# ── L2000 customer followups ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_followup_then_list(
    client: AsyncClient, seeded_tenant, ops_auth_headers
):
    body = {
        "tenant_id": seeded_tenant.id,
        "note": "客户反馈对账系统使用顺畅",
    }
    create = await client.post(
        "/api/v1/ops/customer-followups", json=body, headers=ops_auth_headers
    )
    assert create.status_code == 201
    data = create.json()
    assert data["tenant_id"] == seeded_tenant.id
    assert data["tenant_name"] == seeded_tenant.name

    listing = await client.get(
        "/api/v1/ops/customer-followups", headers=ops_auth_headers
    )
    assert listing.status_code == 200
    assert any(f["id"] == data["id"] for f in listing.json())


@pytest.mark.asyncio
async def test_create_followup_unknown_tenant_404(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.post(
        "/api/v1/ops/customer-followups",
        json={"tenant_id": 999999, "note": "x"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 404


# ── L2001 system announcements ──────────────────────────────────────


@pytest.mark.asyncio
async def test_announcement_create_list_patch_delete(
    client: AsyncClient, ops_auth_headers
):
    create = await client.post(
        "/api/v1/ops/announcements",
        json={"title": "系统升级", "body": "本周末维护", "audience": "all"},
        headers=ops_auth_headers,
    )
    assert create.status_code == 201
    aid = create.json()["id"]

    listing = await client.get("/api/v1/ops/announcements", headers=ops_auth_headers)
    assert any(a["id"] == aid for a in listing.json())

    patch = await client.patch(
        f"/api/v1/ops/announcements/{aid}",
        json={"title": "系统升级（已推迟）"},
        headers=ops_auth_headers,
    )
    assert patch.json()["title"] == "系统升级（已推迟）"

    delete = await client.delete(
        f"/api/v1/ops/announcements/{aid}", headers=ops_auth_headers
    )
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_announcement_invalid_audience_422(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.post(
        "/api/v1/ops/announcements",
        json={"title": "x", "body": "y", "audience": "everyone"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_announcement_state_filter(
    client: AsyncClient, db_session, ops_auth_headers, seeded_user
):
    from app.models.platform import SystemAnnouncement

    db_session.add(
        SystemAnnouncement(title="草稿", body="x", audience="all", created_by=seeded_user.id)
    )
    db_session.add(
        SystemAnnouncement(
            title="已发布",
            body="x",
            audience="all",
            publish_at=datetime.now(UTC) - timedelta(days=1),
            created_by=seeded_user.id,
        )
    )
    db_session.flush()

    drafts = await client.get(
        "/api/v1/ops/announcements?state=draft", headers=ops_auth_headers
    )
    assert all(a["publish_at"] is None for a in drafts.json())


# ── L2002 my own audit log ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_my_audit_logs_only_returns_own_actions(
    client: AsyncClient, db_session, seeded_user, ops_auth_headers
):
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.audit import AuditLog
    from app.models.user import UserAccount

    other = UserAccount(
        phone_enc=encrypt_phone("13900099999"),
        name="另一位运营",
        password_hash=get_password_hash("Other@1234"),
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()

    db_session.add(
        AuditLog(
            actor_user_id=seeded_user.id,
            actor_role="ops",
            tenant_id=None,
            action="me.test",
            target_type="x",
            target_id=1,
        )
    )
    db_session.add(
        AuditLog(
            actor_user_id=other.id,
            actor_role="superadmin",
            tenant_id=None,
            action="other.test",
            target_type="x",
            target_id=2,
        )
    )
    db_session.flush()

    resp = await client.get(
        "/api/v1/ops/audit-logs/me", headers=ops_auth_headers
    )
    assert resp.status_code == 200
    actions = [r["action"] for r in resp.json()["items"]]
    assert "me.test" in actions
    assert "other.test" not in actions


@pytest.mark.asyncio
async def test_ops_extras_require_ops_role(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/settlements/overview", headers=admin_auth_headers
    )
    assert resp.status_code == 403
