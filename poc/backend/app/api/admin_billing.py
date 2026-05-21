"""v0.5.9 — 物业管理员计费视图(分钟数消费 + 存证消费)。

诱因:用户反馈「后端写了需求,前端没实现 — 物业管理员就打电话的分钟数消费金额服务,
还有物业公司第三方存证的消费」。Phase 1 调研发现后端也只有原始数据(TenantMinuteUsage
分钟数 / BlockchainAttestation 存证记录),没有「金额聚合」端点。本模块补齐 4 个聚合
读端点,前端三个新页面消费这些数据。

端点:
- GET /admin/billing/minute-summary?year_month=YYYY-MM  — 本月分钟/金额 KPI
- GET /admin/billing/minute-trend?months=N              — 近 N 月趋势
- GET /admin/billing/blockchain-summary?year_month=YYYY-MM — 本月存证 KPI + 类型分布
- GET /admin/billing/blockchain-attestations            — 存证列表分页

守卫:require_tenant_roles("admin")(物业 admin 专属;服务商 admin 走 /provider/billing)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.billing_pricing import BillingPricing
from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig
from app.models.tenant import Tenant, TenantMinuteUsage
from app.schemas.billing import (
    BlockchainAttestationItem,
    BlockchainSummaryByType,
    BlockchainSummaryOut,
    MinuteSummaryOut,
    MinuteTrendItem,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _active_pricing(db: Session) -> BillingPricing:
    """拿 active BillingPricing 行;无则返回内存默认值(防迁移未跑环境)。"""
    pricing = db.execute(
        select(BillingPricing).where(BillingPricing.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if pricing is not None:
        return pricing
    # 兜底:回 PRD 默认(防止 stats 在 fresh DB 上崩)
    return BillingPricing(
        minute_price_live=Decimal("0.5"),
        minute_price_post=Decimal("0.3"),
        blockchain_price_per_attestation=Decimal("5"),
        blockchain_price_per_case_bundle=Decimal("99"),
        is_active=True,
    )


# ── 分钟数 ────────────────────────────────────────────────────────


@router.get("/billing/minute-summary", response_model=MinuteSummaryOut)
async def minute_summary(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str | None = Query(None, description="YYYY-MM;默认当月"),
) -> MinuteSummaryOut:
    tenant_id = _require_tenant(payload)
    ym = year_month or _current_month()
    pricing = _active_pricing(db)
    usage = db.execute(
        select(TenantMinuteUsage)
        .where(TenantMinuteUsage.tenant_id == tenant_id)
        .where(TenantMinuteUsage.year_month == ym)
    ).scalar_one_or_none()

    realtime = usage.realtime_minutes if usage else 0
    post = usage.post_minutes if usage else 0
    used = usage.used_minutes if usage else (realtime + post)
    quota = usage.quota_at_time if usage and usage.quota_at_time else None
    if quota is None:
        tenant = db.get(Tenant, tenant_id)
        quota = tenant.monthly_minute_quota if tenant else None
    quota_remaining = max(quota - used, 0) if quota is not None else None

    amount_realtime = (Decimal(realtime) * pricing.minute_price_live).quantize(Decimal("0.01"))
    amount_post = (Decimal(post) * pricing.minute_price_post).quantize(Decimal("0.01"))
    return MinuteSummaryOut(
        year_month=ym,
        used_minutes=used,
        realtime_minutes=realtime,
        post_minutes=post,
        price_live=pricing.minute_price_live,
        price_post=pricing.minute_price_post,
        amount_realtime=amount_realtime,
        amount_post=amount_post,
        amount_total=amount_realtime + amount_post,
        quota_total=quota,
        quota_remaining=quota_remaining,
    )


@router.get("/billing/minute-trend", response_model=list[MinuteTrendItem])
async def minute_trend(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    months: int = Query(6, ge=1, le=24),
) -> list[MinuteTrendItem]:
    """近 N 月趋势(返回最近 N 个月,不足则有几月返几月,按时间升序)。"""
    tenant_id = _require_tenant(payload)
    pricing = _active_pricing(db)
    # 算近 N 月 year_month 字符串
    now = datetime.now(UTC)
    months_keys: list[str] = []
    y, m = now.year, now.month
    for _ in range(months):
        months_keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months_keys.reverse()  # 升序

    rows = (
        db.execute(
            select(TenantMinuteUsage)
            .where(TenantMinuteUsage.tenant_id == tenant_id)
            .where(TenantMinuteUsage.year_month.in_(months_keys))
        )
        .scalars()
        .all()
    )
    by_month = {r.year_month: r for r in rows}
    result: list[MinuteTrendItem] = []
    for ym in months_keys:
        row = by_month.get(ym)
        realtime = row.realtime_minutes if row else 0
        post = row.post_minutes if row else 0
        amount = (
            (Decimal(realtime) * pricing.minute_price_live)
            + (Decimal(post) * pricing.minute_price_post)
        ).quantize(Decimal("0.01"))
        result.append(
            MinuteTrendItem(
                year_month=ym,
                realtime_minutes=realtime,
                post_minutes=post,
                amount=amount,
            )
        )
    return result


# ── 存证 ────────────────────────────────────────────────────────


@router.get("/billing/blockchain-summary", response_model=BlockchainSummaryOut)
async def blockchain_summary(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str | None = Query(None),
) -> BlockchainSummaryOut:
    tenant_id = _require_tenant(payload)
    ym = year_month or _current_month()
    # 当月时间区间
    year, month = int(ym[:4]), int(ym[5:7])
    month_start = datetime(year, month, 1, tzinfo=UTC)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    month_end = datetime(next_year, next_month, 1, tzinfo=UTC)

    rows = db.execute(
        select(
            BlockchainAttestation.data_type,
            func.count(BlockchainAttestation.id).label("c"),
            func.coalesce(func.sum(BlockchainAttestation.cost_amount), 0).label("s"),
        )
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .where(BlockchainAttestation.submitted_at >= month_start)
        .where(BlockchainAttestation.submitted_at < month_end)
        .group_by(BlockchainAttestation.data_type)
    ).all()

    by_type: dict[str, BlockchainSummaryByType] = {}
    total_count = 0
    total_amount = Decimal("0.00")
    for data_type, c, s in rows:
        by_type[data_type] = BlockchainSummaryByType(
            count=int(c),
            amount=Decimal(str(s)).quantize(Decimal("0.01")),
        )
        total_count += int(c)
        total_amount += Decimal(str(s))

    # active provider
    config = db.execute(
        select(BlockchainConfig).where(BlockchainConfig.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    chain_provider = config.provider if config else None

    return BlockchainSummaryOut(
        year_month=ym,
        attestation_count=total_count,
        amount_total=total_amount.quantize(Decimal("0.01")),
        by_data_type=by_type,
        chain_provider=chain_provider,
    )


@router.get(
    "/billing/blockchain-attestations",
    response_model=PaginatedResponse[BlockchainAttestationItem],
)
async def blockchain_attestations(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    year_month: str | None = Query(None),
) -> PaginatedResponse[BlockchainAttestationItem]:
    tenant_id = _require_tenant(payload)
    stmt = (
        select(BlockchainAttestation)
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .order_by(BlockchainAttestation.submitted_at.desc())
    )
    if year_month:
        year, month = int(year_month[:4]), int(year_month[5:7])
        month_start = datetime(year, month, 1, tzinfo=UTC)
        next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
        month_end = datetime(next_year, next_month, 1, tzinfo=UTC)
        stmt = stmt.where(BlockchainAttestation.submitted_at >= month_start)
        stmt = stmt.where(BlockchainAttestation.submitted_at < month_end)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.execute(total_stmt).scalar_one() or 0)
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    items = [
        BlockchainAttestationItem(
            id=r.id,
            submitted_at=r.submitted_at,
            case_id=r.legal_case_id,
            data_type=r.data_type,
            cost_amount=r.cost_amount,
            tx_hash=r.tx_hash,
            chain_provider=r.chain_provider,
            status=r.status,
        )
        for r in rows
    ]
    return PaginatedResponse[BlockchainAttestationItem](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# v0.8.0 — 物业 admin 存证风险敞口视图
@router.get("/blockchain/risk-overview")
async def blockchain_risk_overview(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles("admin"))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    top_n: int = Query(10, ge=1, le=50),
) -> dict:
    """物业 admin 存证管理「风险敞口」tab 数据源。

    视角:**不是「我花了多少」而是「我有多少案件证据不够强」**。

    返回:
      - 本月新增案件总数 case_total
      - 已有≥1 件 confirmed 存证(强证据)的案件数 case_with_strong
      - 仅本地哈希(无 confirmed)的案件数 case_local_only
      - 大额且仅本地的高风险案件 Top N(一键上链建议)

    高风险排序:amount_owed × 0.0001 + months_overdue × 0.3 + supervisor_action_count × 2.0
    """
    from sqlalchemy import exists

    from app.models.audit import AuditLog
    from app.models.call import CallRecord as CR
    from app.models.case import CollectionCase, OwnerProfile

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )

    # 本月窗口
    now = datetime.now(UTC)
    if year_month:
        y, m = year_month.split("-")
        month_start = datetime(int(y), int(m), 1, tzinfo=UTC)
    else:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_mon_year = month_start.year + (1 if month_start.month == 12 else 0)
    next_mon = month_start.replace(
        year=next_mon_year,
        month=1 if month_start.month == 12 else month_start.month + 1,
    )

    # 本月新增案件总数
    case_total = int(
        db.execute(
            select(func.count(CollectionCase.id))
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.created_at >= month_start)
            .where(CollectionCase.created_at < next_mon)
        ).scalar_one()
        or 0
    )

    # 已有强证据(任意 confirmed attestation 通过 call_id 关联本案件)的案件数
    strong_subq = (
        select(BlockchainAttestation.id)
        .join(CR, CR.id == BlockchainAttestation.call_id)
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .where(BlockchainAttestation.status == "confirmed")
        .where(CR.case_id == CollectionCase.id)
        .correlate(CollectionCase)
    )
    case_with_strong = int(
        db.execute(
            select(func.count(CollectionCase.id))
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.created_at >= month_start)
            .where(CollectionCase.created_at < next_mon)
            .where(exists(strong_subq))
        ).scalar_one()
        or 0
    )
    case_local_only = max(0, case_total - case_with_strong)

    # Top N 高风险案件(本月新增 + 仅本地哈希 + 非 paid,按风险评分排)
    supervisor_action_subq = (
        select(func.count(AuditLog.id))
        .where(AuditLog.tenant_id == tenant_id)
        .where(AuditLog.target_type == "case")
        .where(AuditLog.target_id == CollectionCase.id)
        .where(AuditLog.action.like("case.supervisor_%"))
        .correlate(CollectionCase)
        .scalar_subquery()
    )
    risk_score_expr = (
        func.coalesce(CollectionCase.amount_owed, 0) * 0.0001
        + func.coalesce(CollectionCase.months_overdue, 0) * 0.3
        + supervisor_action_subq * 2.0
    )

    rows = db.execute(
        select(
            CollectionCase,
            OwnerProfile.name.label("owner_name"),
            OwnerProfile.building,
            OwnerProfile.room,
            supervisor_action_subq.label("supervisor_action_count"),
            risk_score_expr.label("risk_score"),
        )
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
        .where(CollectionCase.created_at >= month_start)
        .where(CollectionCase.created_at < next_mon)
        .where(~exists(strong_subq))
        .where(CollectionCase.stage != "paid")
        .order_by(risk_score_expr.desc())
        .limit(top_n)
    ).all()

    high_value_local_only = [
        {
            "case_id": r.CollectionCase.id,
            "owner_name": r.owner_name,
            "building_room": (r.building or "") + (r.room or ""),
            "amount_owed": str(r.CollectionCase.amount_owed)
            if r.CollectionCase.amount_owed is not None
            else "0",
            "months_overdue": r.CollectionCase.months_overdue or 0,
            "stage": r.CollectionCase.stage,
            "supervisor_action_count": int(r.supervisor_action_count or 0),
            "last_contact_at": (
                r.CollectionCase.last_contact_at.isoformat()
                if r.CollectionCase.last_contact_at
                else None
            ),
        }
        for r in rows
    ]

    return {
        "year_month": month_start.strftime("%Y-%m"),
        "case_total": case_total,
        "case_with_strong": case_with_strong,
        "case_local_only": case_local_only,
        "strong_pct": (round(case_with_strong / case_total * 100, 1) if case_total > 0 else 0.0),
        "high_value_local_only": high_value_local_only,
    }
