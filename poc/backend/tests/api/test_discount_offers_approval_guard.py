"""§9.2 Task 3 — 减免 approve/reject/escalate 收紧为物业侧专属。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _pending_offer(db_session, tenant_id, case_id):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=tenant_id,
        case_id=case_id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal("700.00"),
        discount_pct=30,
        reason="测试审批守卫用减免",
        status="pending_supervisor",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        audit_trail=[],
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def _provider_supervisor_headers(db_session, tenant_id):
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="审批守卫测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092020"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()
    user = UserAccount(
        phone_enc=encrypt_phone("13900092021"),
        name="服务商督导",
        password_hash=get_password_hash("Super@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role="supervisor",
            provider_id=provider.id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": "supervisor",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_provider_supervisor_cannot_approve(client, db_session, seeded_tenant, seeded_case):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/approve", json={}, headers=headers
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_provider_supervisor_cannot_reject(client, db_session, seeded_tenant, seeded_case):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/reject",
        json={"reason": "驳回理由"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_provider_supervisor_cannot_escalate(client, db_session, seeded_tenant, seeded_case):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    headers = _provider_supervisor_headers(db_session, seeded_tenant.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/escalate", json={}, headers=headers
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_property_supervisor_can_approve(
    client, db_session, seeded_tenant, seeded_case, supervisor_auth_headers
):
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/approve",
        json={},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_property_agent_cannot_approve(
    client, db_session, seeded_tenant, seeded_case, agent_auth_headers
):
    """角色维度收紧：物业内勤 agent（改造前在 ALL_ROLES 内）现在应被挡。"""
    offer = _pending_offer(db_session, seeded_tenant.id, seeded_case.id)
    resp = await client.post(
        f"/api/v1/discount-offers/{offer.id}/approve", json={}, headers=agent_auth_headers
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_FORBIDDEN"
