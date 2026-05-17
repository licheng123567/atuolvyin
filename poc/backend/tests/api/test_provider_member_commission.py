"""§9.2 Task 6 — /provider/team/{id}/commission 逐案实收×服务商项目率。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _seed(db_session, seeded_tenant, seeded_owner):
    """造：服务商 + 服务商 admin（调用方）+ 团队成员 + 2 个项目 + 2 个已付案件 + 1 条已执行减免。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.case import CollectionCase, Project
    from app.models.discount_offer import DiscountOffer
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="服务商佣金测试",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900092030"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()

    caller = UserAccount(
        phone_enc=encrypt_phone("13900092031"),
        name="服务商管理员",
        password_hash=get_password_hash("Admin@1234"),
        is_active=True,
    )
    member = UserAccount(
        phone_enc=encrypt_phone("13900092032"),
        name="服务商催收员",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add_all([caller, member])
    db_session.flush()
    db_session.add_all(
        [
            UserTenantMembership(
                user_id=caller.id,
                tenant_id=seeded_tenant.id,
                role="admin",
                provider_id=provider.id,
                is_active=True,
            ),
            UserTenantMembership(
                user_id=member.id,
                tenant_id=seeded_tenant.id,
                role="agent",
                work_mode="external",
                provider_id=provider.id,
                is_active=True,
            ),
        ]
    )

    p1 = Project(
        tenant_id=seeded_tenant.id,
        name="服务商项目甲",
        provider_id=provider.id,
        provider_agent_commission_rate=Decimal("0.1000"),
    )
    p2 = Project(tenant_id=seeded_tenant.id, name="服务商项目乙", provider_id=provider.id)
    db_session.add_all([p1, p2])
    db_session.flush()

    c1 = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        project_id=p1.id,
        assigned_to=member.id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal("1000.00"),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    c2 = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        project_id=p2.id,
        assigned_to=member.id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal("2000.00"),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    db_session.add(
        DiscountOffer(
            tenant_id=seeded_tenant.id,
            case_id=c1.id,
            provider_id=provider.id,
            applicant_user_id=None,
            applicant_role="agent",
            offer_type="principal_discount",
            original_amount=Decimal("1000.00"),
            proposed_amount=Decimal("600.00"),
            discount_pct=40,
            reason="服务商佣金测试减免",
            status="executed",
            approver_role_required="supervisor",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            audit_trail=[],
        )
    )
    db_session.flush()

    token = create_access_token(
        {
            "sub": str(caller.id),
            "user_id": caller.id,
            "tenant_id": None,
            "role": "admin",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}, member.id


@pytest.mark.asyncio
async def test_provider_member_commission_per_case(client, db_session, seeded_tenant, seeded_owner):
    headers, member_id = _seed(db_session, seeded_tenant, seeded_owner)

    resp = await client.get(
        f"/api/v1/provider/team/{member_id}/commission?year_month=2026-05", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # base = 实收 600 + 2000 = 2600
    assert Decimal(str(body["base_amount"])) == Decimal("2600.00")
    # commission = (600*0.10).q(.01) + (2000*0.05).q(.01) = 60.00 + 100.00
    assert Decimal(str(body["commission"])) == Decimal("160.00")
    assert len(body["items"]) == 2

    by_amount = {Decimal(str(it["paid_amount"])): it for it in body["items"]}
    # C1 实收 600，项目率 0.10
    assert Decimal(str(by_amount[Decimal("600.00")]["commission_rate"])) == Decimal("0.1000")
    # C2 实收 2000，项目无率 → 默认 0.05
    assert Decimal(str(by_amount[Decimal("2000.00")]["commission_rate"])) == Decimal("0.0500")
