"""v0.5.9 — 服务商管理员跨租户分钟消费测试。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.crypto import encrypt_phone


@pytest.fixture
def seeded_pricing(db_session):
    from app.models.billing_pricing import BillingPricing
    from sqlalchemy import select
    existing = db_session.execute(
        select(BillingPricing).where(BillingPricing.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if existing:
        return existing
    p = BillingPricing(
        minute_price_live=Decimal("0.5"),
        minute_price_post=Decimal("0.3"),
        blockchain_price_per_attestation=Decimal("5"),
        blockchain_price_per_case_bundle=Decimal("99"),
        is_active=True,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_provider_setup(db_session, seeded_tenant):
    """v0.5.9 — provider + 2 个合作租户 + 每个租户 active 合约 + 分钟用量。"""
    from app.core.security import get_password_hash
    from app.models.tenant import (
        ProviderTenantContract, ServiceProvider, Tenant,
        TenantMinuteUsage, UserTenantMembership,
    )
    from app.models.user import UserAccount

    # provider
    p = ServiceProvider(
        name="v0.5.9 测试服务商 X",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900059001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()

    # tenant2(用 seeded_tenant 作为 tenant1)
    t2 = Tenant(
        name="v0.5.9 第二租户", credit_code="DEMO000000000059",
        admin_phone_enc=encrypt_phone("13900059002"), is_active=True,
    )
    db_session.add(t2)
    db_session.flush()

    # active contracts
    now = datetime.now(UTC)
    for t in (seeded_tenant, t2):
        c = ProviderTenantContract(
            tenant_id=t.id, provider_id=p.id,
            signed_at=now - timedelta(days=30),
            service_types=["collection"], status="active",
        )
        db_session.add(c)

    # 分钟用量:tenant1 realtime 200 / post 100;tenant2 realtime 50 / post 50
    ym = now.strftime("%Y-%m")
    from sqlalchemy import select
    for t, rt, ps in [(seeded_tenant, 200, 100), (t2, 50, 50)]:
        existing = db_session.execute(
            select(TenantMinuteUsage)
            .where(TenantMinuteUsage.tenant_id == t.id)
            .where(TenantMinuteUsage.year_month == ym)
        ).scalar_one_or_none()
        if existing:
            existing.realtime_minutes = rt
            existing.post_minutes = ps
            existing.used_minutes = rt + ps
        else:
            db_session.add(TenantMinuteUsage(
                tenant_id=t.id, year_month=ym,
                realtime_minutes=rt, post_minutes=ps, used_minutes=rt + ps,
            ))

    # provider admin 账号 + membership
    user = UserAccount(
        phone_enc=encrypt_phone("13900059010"),
        name="v0.5.9 provider admin",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserTenantMembership(
        user_id=user.id, tenant_id=seeded_tenant.id,
        role="admin", provider_id=p.id, is_active=True,
    ))
    db_session.flush()
    return {"provider": p, "tenants": [seeded_tenant, t2], "user": user}


@pytest.fixture
def provider_auth_headers_x(seeded_provider_setup):
    from app.core.security import create_access_token
    user = seeded_provider_setup["user"]
    provider = seeded_provider_setup["provider"]
    token = create_access_token({
        "sub": str(user.id), "user_id": user.id,
        "tenant_id": None, "role": "admin",
        "provider_id": provider.id,
        "scope": f"provider:{provider.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_provider_minute_summary_cross_tenant(
    client: AsyncClient, seeded_pricing, seeded_provider_setup, provider_auth_headers_x,
):
    """provider 接 2 个 tenant,看到 2 行明细 + 总额正确。"""
    resp = await client.get(
        "/api/v1/provider/billing/minute-summary",
        headers=provider_auth_headers_x,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tenants"]) == 2
    # tenant1(200 RT + 100 PT)= 200×0.5 + 100×0.3 = 100 + 30 = 130
    # tenant2(50 RT + 50 PT) = 50×0.5 + 50×0.3 = 25 + 15 = 40
    # total = 170 元 / 400 分钟
    assert data["minute_total"] == 400
    assert Decimal(data["amount_total"]) == Decimal("170.00")
    # 按金额降序;tenant1 应在前
    assert Decimal(data["tenants"][0]["amount"]) == Decimal("130.00")
    assert Decimal(data["tenants"][1]["amount"]) == Decimal("40.00")


@pytest.mark.asyncio
async def test_provider_blocked_from_admin_billing(
    client: AsyncClient, seeded_provider_setup, provider_auth_headers_x,
):
    """服务商 admin token 不能调 /admin/billing/* 端点(物业专属)。"""
    resp = await client.get(
        "/api/v1/admin/billing/minute-summary", headers=provider_auth_headers_x,
    )
    assert resp.status_code == 403
