"""v0.5.9 — 物业 admin 计费端点测试。

覆盖:
- minute-summary 单价 × 分钟数 = 金额(实时 + 事后分开)
- minute-trend 返回近 N 月
- blockchain-summary 按 data_type 分组
- blockchain-attestations 分页列表
- 守卫:物业 admin token OK,物业 admin 调 /provider/billing → 403
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_pricing(db_session):
    """种 active BillingPricing(若 migration 没插或者被 reset 清掉)。"""
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
def seeded_minute_usage(db_session, seeded_tenant):
    """本月 TenantMinuteUsage:realtime=120 / post=80 = 200 分钟。"""
    from app.models.tenant import TenantMinuteUsage
    from sqlalchemy import select
    ym = datetime.now(UTC).strftime("%Y-%m")
    # 清旧的(seed_demo 可能种了一行)
    existing = db_session.execute(
        select(TenantMinuteUsage)
        .where(TenantMinuteUsage.tenant_id == seeded_tenant.id)
        .where(TenantMinuteUsage.year_month == ym)
    ).scalar_one_or_none()
    if existing:
        existing.realtime_minutes = 120
        existing.post_minutes = 80
        existing.used_minutes = 200
        db_session.flush()
        return existing
    u = TenantMinuteUsage(
        tenant_id=seeded_tenant.id, year_month=ym,
        realtime_minutes=120, post_minutes=80, used_minutes=200, quota_at_time=5000,
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def seeded_attestations(db_session, seeded_tenant):
    """本月 3 条 attestation:2 个 call_recording(各 ¥5) + 1 个 evidence_bundle(¥99)。"""
    from app.models.blockchain_attestation import BlockchainAttestation
    now = datetime.now(UTC)
    for i, (dtype, cost) in enumerate([
        ("call_recording", Decimal("5")),
        ("call_recording", Decimal("5")),
        ("evidence_bundle", Decimal("99")),
    ]):
        db_session.add(BlockchainAttestation(
            tenant_id=seeded_tenant.id,
            data_sha256=f"{'a' * 60}{i:04d}",
            data_type=dtype,
            chain_provider="mock",
            chain_endpoint="https://mock.test",
            tx_hash=f"{'b' * 60}{i:04d}",
            block_height=1000 + i,
            status="confirmed",
            submitted_at=now,
            confirmed_at=now,
            cost_amount=cost,
        ))
    db_session.flush()


# ── minute summary ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_minute_summary_calculates_amount(
    client: AsyncClient, admin_auth_headers, seeded_pricing, seeded_minute_usage,
):
    resp = await client.get(
        "/api/v1/admin/billing/minute-summary", headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["realtime_minutes"] == 120
    assert data["post_minutes"] == 80
    assert data["used_minutes"] == 200
    # 120 × 0.5 = 60.00
    assert Decimal(data["amount_realtime"]) == Decimal("60.00")
    # 80 × 0.3 = 24.00
    assert Decimal(data["amount_post"]) == Decimal("24.00")
    assert Decimal(data["amount_total"]) == Decimal("84.00")


@pytest.mark.asyncio
async def test_minute_trend_returns_n_months(
    client: AsyncClient, admin_auth_headers, seeded_pricing, seeded_minute_usage,
):
    resp = await client.get(
        "/api/v1/admin/billing/minute-trend?months=3", headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # 最后一项是当月(应该有 200 分钟)
    assert data[-1]["realtime_minutes"] == 120


# ── blockchain summary ────────────────────────────────────────


@pytest.mark.asyncio
async def test_blockchain_summary_groups_by_type(
    client: AsyncClient, admin_auth_headers, seeded_attestations,
):
    resp = await client.get(
        "/api/v1/admin/billing/blockchain-summary", headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["attestation_count"] == 3
    # 2 × 5 + 1 × 99 = 109
    assert Decimal(data["amount_total"]) == Decimal("109.00")
    assert "call_recording" in data["by_data_type"]
    assert data["by_data_type"]["call_recording"]["count"] == 2
    assert Decimal(data["by_data_type"]["evidence_bundle"]["amount"]) == Decimal("99.00")


@pytest.mark.asyncio
async def test_blockchain_attestations_list_pagination(
    client: AsyncClient, admin_auth_headers, seeded_attestations,
):
    resp = await client.get(
        "/api/v1/admin/billing/blockchain-attestations?page=1&page_size=2",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    # 按 submitted_at desc 排;item 应该有 cost_amount
    assert data["items"][0]["cost_amount"] is not None


# ── 守卫边界 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_blocked_from_provider_endpoint(
    client: AsyncClient, admin_auth_headers,
):
    """物业 admin token 不能调 /provider/billing/* 端点(provider_id 是 None)。"""
    resp = await client.get(
        "/api/v1/provider/billing/minute-summary", headers=admin_auth_headers,
    )
    assert resp.status_code == 403
