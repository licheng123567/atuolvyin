"""§9.2 Task 2 — 减免归属：create 写 provider_id + DiscountOfferOut 透出。"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone


def _provider(db_session):
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="归属测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092010"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


def _provider_agent_headers(db_session, tenant_id, provider_id):
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900092011"),
        name="服务商催收员",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role="agent",
            work_mode="external",
            provider_id=provider_id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": "agent",
            "provider_id": provider_id,
            "scope": f"provider:{provider_id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


_BODY = {
    "offer_type": "principal_discount",
    "original_amount": "1000.00",
    "proposed_amount": "800.00",
    "reason": "业主主张房屋空置，申请减免",
}


@pytest.mark.asyncio
async def test_provider_agent_offer_carries_provider_id(
    client, db_session, seeded_tenant, seeded_case
):
    provider = _provider(db_session)
    headers = _provider_agent_headers(db_session, seeded_tenant.id, provider.id)

    resp = await client.post(
        f"/api/v1/cases/{seeded_case.id}/discount-offers", json=_BODY, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_id"] == provider.id


@pytest.mark.asyncio
async def test_property_agent_offer_provider_id_null(
    client, seeded_case, agent_auth_headers
):
    resp = await client.post(
        f"/api/v1/cases/{seeded_case.id}/discount-offers",
        json=_BODY,
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_id"] is None
