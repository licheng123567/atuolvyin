"""v2.2 — 发送缴费链接：坐席端 + 物业管理端共用 send-payment-link 端点。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _other_tenant_case(db_session):
    """造一个属于另一租户的案件（含 owner），返回 case。"""
    from app.models.case import CollectionCase, OwnerProfile
    from app.models.tenant import Tenant

    other = Tenant(
        name="另一物业公司",
        admin_phone_enc=encrypt_phone("13900139777"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    owner = OwnerProfile(
        tenant_id=other.id,
        name="李四",
        phone_enc=encrypt_phone("13712340000"),
        building="2栋",
        room="202",
    )
    db_session.add(owner)
    db_session.flush()
    case = CollectionCase(
        tenant_id=other.id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("1000.00"),
        months_overdue=2,
        priority_score=900,
    )
    db_session.add(case)
    db_session.flush()
    return case


# ── 坐席端 /agent/cases/{id}/send-payment-link ──────────────────────────


@pytest.mark.asyncio
async def test_agent_sends_payment_link_for_own_case(
    client, seeded_assigned_case, agent_auth_headers
):
    """坐席给分配给自己的案件发缴费链接 → 201 + 返回 link / short_link。"""
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_assigned_case.id}/send-payment-link",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == seeded_assigned_case.id
    assert body["link"].startswith("https://")
    assert body["short_link"].startswith("https://")
    assert body["sms_status"] == "queued"


@pytest.mark.asyncio
async def test_agent_cannot_send_for_unassigned_case(
    client, seeded_case, agent_auth_headers
):
    """案件未分配给该坐席 → 403。"""
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/send-payment-link",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


# ── 物业管理端 /admin/cases/{id}/send-payment-link ──────────────────────


@pytest.mark.asyncio
async def test_admin_sends_payment_link_for_any_tenant_case(
    client, seeded_case, admin_auth_headers
):
    """管理员对本租户任意案件发缴费链接（不要求 assigned_to）→ 201。"""
    resp = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/send-payment-link",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == seeded_case.id
    assert body["short_link"].startswith("https://")
    assert body["sms_status"] == "queued"


@pytest.mark.asyncio
async def test_supervisor_can_send_payment_link(
    client, seeded_case, supervisor_auth_headers
):
    """督导也可发送缴费链接 → 201。"""
    resp = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/send-payment-link",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_admin_cannot_send_for_cross_tenant_case(
    client, db_session, admin_auth_headers
):
    """跨租户案件 → 404（租户隔离）。"""
    other_case = _other_tenant_case(db_session)
    resp = await client.post(
        f"/api/v1/admin/cases/{other_case.id}/send-payment-link",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"
