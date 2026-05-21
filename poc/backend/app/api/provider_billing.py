"""v0.5.9 — 服务商管理员跨租户分钟消费视图。

用户决策:服务商看「我接了 N 个租户,每个贡献多少分钟」 — 不是「服务商自己的配额」,
而是「我服务的所有租户的分钟用量汇总,分租户列明细」。

逻辑:
1. 拿当前用户 provider_id(从 token 或 UserTenantMembership)
2. 查 ProviderTenantContract 找出 active 合作的 tenant_id 列表
3. 查 TenantMinuteUsage 按 tenant_id 分组拿本月分钟数
4. 按 BillingPricing 单价计算每租户的金额 + 总额

守卫:require_provider_roles("admin")。物业 admin 调本端点会被 require_provider_roles
直接拒绝(403),不会泄露数据。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_provider_roles
from app.models.billing_pricing import BillingPricing
from app.models.tenant import (
    ProviderTenantContract,
    Tenant,
    TenantMinuteUsage,
    UserTenantMembership,
)
from app.schemas.billing import ProviderMinuteSummaryOut, ProviderMinuteTenantItem

router = APIRouter()


def _resolve_provider_id(user_id: int, db: Session) -> int:
    """与 provider_admin._resolve_provider_id / provider_cases._resolve_provider_id 同源。"""
    membership = (
        db.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.user_id == user_id)
            .where(UserTenantMembership.provider_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if membership is None or membership.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_NO_PROVIDER",
                "message": "当前账号未绑定任何服务商",
            },
        )
    return int(membership.provider_id)


def _user_id_from_payload(payload: dict) -> int:
    uid = payload.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token missing user_id"},
        )
    return int(uid)


def _active_pricing(db: Session) -> BillingPricing:
    pricing = db.execute(
        select(BillingPricing).where(BillingPricing.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if pricing is not None:
        return pricing
    return BillingPricing(
        minute_price_live=Decimal("0.5"),
        minute_price_post=Decimal("0.3"),
        blockchain_price_per_attestation=Decimal("5"),
        blockchain_price_per_case_bundle=Decimal("99"),
        is_active=True,
    )


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


@router.get("/billing/minute-summary", response_model=ProviderMinuteSummaryOut)
async def provider_minute_summary(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str | None = Query(None),
) -> ProviderMinuteSummaryOut:
    """跨租户分钟消费明细 — 本服务商接的所有 active 合作租户。"""
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)
    ym = year_month or _current_month()
    pricing = _active_pricing(db)

    # 1. active 合作租户 id 列表
    rows = db.execute(
        select(ProviderTenantContract.tenant_id, Tenant.name)
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(ProviderTenantContract.provider_id == provider_id)
        .where(ProviderTenantContract.status == "active")
    ).all()
    if not rows:
        return ProviderMinuteSummaryOut(
            year_month=ym,
            tenants=[],
            minute_total=0,
            amount_total=Decimal("0.00"),
            price_live=pricing.minute_price_live,
            price_post=pricing.minute_price_post,
        )

    tenant_id_to_name = {tid: tname for tid, tname in rows}
    tenant_ids = list(tenant_id_to_name.keys())

    # 2. 该月各租户用量
    usage_rows = (
        db.execute(
            select(TenantMinuteUsage)
            .where(TenantMinuteUsage.tenant_id.in_(tenant_ids))
            .where(TenantMinuteUsage.year_month == ym)
        )
        .scalars()
        .all()
    )
    usage_by_tenant = {u.tenant_id: u for u in usage_rows}

    # 3. 按租户聚合 + 金额
    items: list[ProviderMinuteTenantItem] = []
    minute_total = 0
    amount_total = Decimal("0.00")
    for tid in tenant_ids:
        u = usage_by_tenant.get(tid)
        realtime = u.realtime_minutes if u else 0
        post = u.post_minutes if u else 0
        amount = (
            (Decimal(realtime) * pricing.minute_price_live)
            + (Decimal(post) * pricing.minute_price_post)
        ).quantize(Decimal("0.01"))
        items.append(
            ProviderMinuteTenantItem(
                tenant_id=tid,
                tenant_name=tenant_id_to_name[tid],
                realtime_minutes=realtime,
                post_minutes=post,
                amount=amount,
            )
        )
        minute_total += realtime + post
        amount_total += amount

    # 按金额降序便于看「谁贡献最多」
    items.sort(key=lambda i: i.amount, reverse=True)

    return ProviderMinuteSummaryOut(
        year_month=ym,
        tenants=items,
        minute_total=minute_total,
        amount_total=amount_total,
        price_live=pricing.minute_price_live,
        price_post=pricing.minute_price_post,
    )
