"""v0.5.9 — 计费 API 响应 schema(物业 admin + 服务商 admin 视角)。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MinuteSummaryOut(BaseModel):
    """GET /admin/billing/minute-summary 响应。"""

    year_month: str
    used_minutes: int
    realtime_minutes: int
    post_minutes: int
    price_live: Decimal
    price_post: Decimal
    amount_realtime: Decimal
    amount_post: Decimal
    amount_total: Decimal
    quota_total: int | None
    quota_remaining: int | None


class MinuteTrendItem(BaseModel):
    year_month: str
    realtime_minutes: int
    post_minutes: int
    amount: Decimal


class BlockchainSummaryByType(BaseModel):
    count: int
    amount: Decimal


class BlockchainSummaryOut(BaseModel):
    """GET /admin/billing/blockchain-summary 响应。"""

    year_month: str
    attestation_count: int
    amount_total: Decimal
    by_data_type: dict[str, BlockchainSummaryByType]
    chain_provider: str | None  # active provider name


class BlockchainAttestationItem(BaseModel):
    id: int
    submitted_at: datetime
    case_id: int | None
    data_type: str
    cost_amount: Decimal | None
    tx_hash: str | None
    chain_provider: str
    status: str


class ProviderMinuteTenantItem(BaseModel):
    tenant_id: int
    tenant_name: str
    realtime_minutes: int
    post_minutes: int
    amount: Decimal


class ProviderMinuteSummaryOut(BaseModel):
    """GET /provider/billing/minute-summary 响应。"""

    year_month: str
    tenants: list[ProviderMinuteTenantItem]
    minute_total: int
    amount_total: Decimal
    price_live: Decimal
    price_post: Decimal
