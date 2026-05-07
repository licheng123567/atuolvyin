"""Sprint 14 — provider_admin (服务商工作台) router.

A `provider_admin` user is the manager of a ServiceProvider organisation
(e.g. a 法务公司). Their resource scope is the provider — not a tenant —
resolved by joining UserTenantMembership.provider_id.

Endpoints (all under /api/v1/provider):
    GET    /dashboard/stats         provider KPI snapshot
    GET    /tenants                 partner tenants list
    GET    /team                    provider staff list
    GET    /team/{user_id}          single team member
    PATCH  /team/{user_id}/active   toggle team member active flag
    GET    /settlements             read-only settlement list
    GET    /settlements/{id}        read-only settlement detail (+disputes)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_password_hash, get_token_payload, require_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.models.settlement import DisputeRecord, SettlementStatement
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    Tenant,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider_admin import (
    CommissionLineItem,
    ProviderContractSummary,
    ProviderDashboardStats,
    ProviderDisputeIn,
    ProviderDisputeOut,
    ProviderMemberCommission,
    ProviderMemberPerformance,
    ProviderSettlementDetailOut,
    ProviderSettlementOut,
    ProviderTeamMemberDetailOut,
    ProviderTeamMemberOut,
    ProviderTenantOut,
    TeamActiveIn,
    TeamMemberCreateIn,
)
from app.schemas.settlement import DisputeOut

DEFAULT_COMMISSION_RATE = 0.05  # MVP fallback; future: pull from membership.commission_rate
PERFORMANCE_DEFAULT_DAYS = 30

router = APIRouter()

PROVIDER_ROLES = ("provider_admin",)


# ── helpers ──────────────────────────────────────────────────────────


def _resolve_provider_id(user_id: int, db: Session) -> int:
    """Find the provider_id linked to a provider_admin user.

    Returns 404 ERR_NO_PROVIDER if the user has no membership row with
    a non-null provider_id (account misconfigured).
    """
    membership = db.execute(
        select(UserTenantMembership)
        .where(UserTenantMembership.user_id == user_id)
        .where(UserTenantMembership.provider_id.isnot(None))
    ).scalars().first()
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
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token payload"},
        )
    return int(user_id)


def _settlement_to_out(
    s: SettlementStatement,
    contract: ProviderTenantContract,
    tenant: Tenant,
) -> ProviderSettlementOut:
    return ProviderSettlementOut(
        id=s.id,
        contract_id=s.contract_id,
        tenant_id=contract.tenant_id,
        tenant_name=tenant.name,
        period_start=s.period_start,
        period_end=s.period_end,
        total_amount=s.total_amount,
        status=s.status,  # type: ignore[arg-type]
        payment_proof_url=s.payment_proof_url,
        confirmed_at=s.confirmed_at,
        paid_at=s.paid_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _team_member_to_out(
    user: UserAccount, role: str, membership_active: bool
) -> ProviderTeamMemberOut:
    """Build the team member DTO. `is_active` reflects the membership state
    for the provider scope, not the user account flag — so a deactivated
    membership shows as inactive even if the underlying account is alive."""
    return ProviderTeamMemberOut(
        user_id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=role,
        is_active=membership_active and user.is_active,
        created_at=user.created_at,
    )


# ── PA.3.1 dashboard ─────────────────────────────────────────────────


@router.get("/dashboard/stats", response_model=ProviderDashboardStats)
async def get_provider_dashboard(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderDashboardStats:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    provider = db.get(ServiceProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "服务商不存在"},
        )

    # 合作租户数 — distinct partner tenants with active contracts
    partner_tenant_count: int = db.execute(
        select(func.count(func.distinct(ProviderTenantContract.tenant_id)))
        .where(ProviderTenantContract.provider_id == provider_id)
    ).scalar_one() or 0

    # 团队人数 — active memberships under this provider
    team_count: int = db.execute(
        select(func.count(UserTenantMembership.id))
        .where(UserTenantMembership.provider_id == provider_id)
    ).scalar_one() or 0

    # Current month boundaries
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    # 本月收入 — sum of PAID settlements where paid_at falls in current month
    revenue_month: Decimal = db.execute(
        select(func.coalesce(func.sum(SettlementStatement.total_amount), 0))
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            ProviderTenantContract.provider_id == provider_id,
            SettlementStatement.status == "PAID",
            SettlementStatement.paid_at >= month_start,
            SettlementStatement.paid_at < next_month,
        )
    ).scalar_one() or Decimal("0")

    # 待结算金额 — DRAFT + CONFIRMED (not yet paid)
    pending_total: Decimal = db.execute(
        select(func.coalesce(func.sum(SettlementStatement.total_amount), 0))
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            ProviderTenantContract.provider_id == provider_id,
            SettlementStatement.status.in_(("DRAFT", "CONFIRMED")),
        )
    ).scalar_one() or Decimal("0")

    # Top 10 active contracts
    contract_rows = db.execute(
        select(ProviderTenantContract, Tenant)
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(ProviderTenantContract.provider_id == provider_id)
        .order_by(ProviderTenantContract.signed_at.desc())
        .limit(10)
    ).all()
    contracts = [
        ProviderContractSummary(
            tenant_id=t.id,
            tenant_name=t.name,
            status=c.status,
            signed_at=c.signed_at,
            expires_at=c.expires_at,
        )
        for c, t in contract_rows
    ]

    return ProviderDashboardStats(
        provider_name=provider.name,
        partner_tenant_count=partner_tenant_count,
        team_count=team_count,
        revenue_month=Decimal(str(revenue_month)),
        pending_settlement_total=Decimal(str(pending_total)),
        contracts=contracts,
    )


# ── PA.3.2 partner tenants ──────────────────────────────────────────


@router.get("/tenants", response_model=PaginatedResponse[ProviderTenantOut])
async def list_partner_tenants(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern=r"^(active|expired)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderTenantOut]:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    stmt = (
        select(ProviderTenantContract, Tenant)
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(ProviderTenantContract.provider_id == provider_id)
    )
    if q:
        stmt = stmt.where(Tenant.name.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(ProviderTenantContract.status == status)

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.order_by(ProviderTenantContract.signed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        ProviderTenantOut(
            tenant_id=t.id,
            name=t.name,
            contract_id=c.id,
            signed_at=c.signed_at,
            expires_at=c.expires_at,
            status=c.status,
            service_types=list(c.service_types or []),
        )
        for c, t in rows
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# ── PA.3.3 team management ──────────────────────────────────────────


@router.post(
    "/team",
    response_model=ProviderTeamMemberOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_team_member(
    body: TeamMemberCreateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderTeamMemberOut:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # tenant must be a partner the provider has an active contract with
    contract = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.provider_id == provider_id,
            ProviderTenantContract.tenant_id == body.tenant_id,
            ProviderTenantContract.status == "active",
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NO_CONTRACT",
                "message": "未与该租户建立合作合同",
            },
        )

    new_user = UserAccount(
        phone_enc=encrypt_phone(body.phone),
        name=body.name,
        password_hash=get_password_hash(body.password),
        is_active=True,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_DUPLICATE_PHONE", "message": "手机号已被注册"},
        ) from None

    membership = UserTenantMembership(
        user_id=new_user.id,
        tenant_id=body.tenant_id,
        role=body.role,
        source_type="PROVIDER",
        provider_id=provider_id,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)
    return _team_member_to_out(new_user, body.role, True)


@router.get(
    "/team", response_model=PaginatedResponse[ProviderTeamMemberOut]
)
async def list_team_members(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderTeamMemberOut]:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    stmt = (
        select(
            UserAccount,
            UserTenantMembership.role,
            UserTenantMembership.is_active,
        )
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(UserTenantMembership.provider_id == provider_id)
    )

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.order_by(UserAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        _team_member_to_out(user, role, m_active) for user, role, m_active in rows
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/team/{member_user_id}", response_model=ProviderTeamMemberDetailOut
)
async def get_team_member(
    member_user_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderTeamMemberDetailOut:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(
            UserAccount,
            UserTenantMembership.role,
            UserTenantMembership.is_active,
        )
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == member_user_id,
            UserTenantMembership.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "团队成员不存在"},
        )
    user, role, m_active = row
    base = _team_member_to_out(user, role, m_active)
    return ProviderTeamMemberDetailOut(**base.model_dump())


@router.patch(
    "/team/{member_user_id}/active",
    response_model=ProviderTeamMemberOut,
)
async def toggle_team_member_active(
    member_user_id: int,
    body: TeamActiveIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderTeamMemberOut:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    if member_user_id == user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_CANNOT_DEACTIVATE_SELF",
                "message": "不能停用自己的账号",
            },
        )

    row = db.execute(
        select(UserAccount, UserTenantMembership)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == member_user_id,
            UserTenantMembership.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "团队成员不存在"},
        )
    user, membership = row
    membership.is_active = body.is_active
    db.commit()
    db.refresh(membership)
    db.refresh(user)
    return _team_member_to_out(user, membership.role, membership.is_active)


# ── PA.3.4 settlements (read-only) ──────────────────────────────────


@router.get(
    "/settlements", response_model=PaginatedResponse[ProviderSettlementOut]
)
async def list_provider_settlements(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(
        None, description="DRAFT/CONFIRMED/PAID/DISPUTED"
    ),
    year_month: str | None = Query(
        None, description="YYYY-MM, filters by period_start"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderSettlementOut]:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    stmt = (
        select(SettlementStatement, ProviderTenantContract, Tenant)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(ProviderTenantContract.provider_id == provider_id)
    )
    if status:
        stmt = stmt.where(SettlementStatement.status == status)
    if year_month:
        try:
            year, month = year_month.split("-")
            year_i, month_i = int(year), int(month)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "ERR_VALIDATION",
                    "message": "year_month 格式应为 YYYY-MM",
                },
            ) from None
        period_lo = datetime(year_i, month_i, 1, tzinfo=UTC)
        if month_i == 12:
            period_hi = datetime(year_i + 1, 1, 1, tzinfo=UTC)
        else:
            period_hi = datetime(year_i, month_i + 1, 1, tzinfo=UTC)
        stmt = stmt.where(
            SettlementStatement.period_start >= period_lo,
            SettlementStatement.period_start < period_hi,
        )

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.order_by(
            SettlementStatement.period_start.desc(),
            SettlementStatement.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [_settlement_to_out(s, c, t) for s, c, t in rows]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/settlements/{statement_id}",
    response_model=ProviderSettlementDetailOut,
)
async def get_provider_settlement(
    statement_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderSettlementDetailOut:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(SettlementStatement, ProviderTenantContract, Tenant)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(
            SettlementStatement.id == statement_id,
            ProviderTenantContract.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "结算单不存在"},
        )
    s, c, t = row

    disputes = db.execute(
        select(DisputeRecord)
        .where(DisputeRecord.statement_id == statement_id)
        .order_by(DisputeRecord.id.desc())
    ).scalars().all()

    base = _settlement_to_out(s, c, t)
    return ProviderSettlementDetailOut(
        **base.model_dump(),
        disputes=[DisputeOut.model_validate(d) for d in disputes],
    )


# ── PA.3.5 — Sprint 9.3 — submit settlement dispute ─────────────────


@router.post(
    "/settlements/{statement_id}/dispute",
    response_model=ProviderDisputeOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def submit_dispute(
    statement_id: int,
    body: ProviderDisputeIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderDisputeOut:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(SettlementStatement, ProviderTenantContract)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            SettlementStatement.id == statement_id,
            ProviderTenantContract.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "结算单不存在"},
        )
    statement, _contract = row

    if statement.status not in ("DRAFT", "CONFIRMED", "DISPUTED"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_TRANSITION",
                "message": "已结清的结算单不能再提交异议",
            },
        )

    dispute = DisputeRecord(
        statement_id=statement_id,
        reason=body.reason,
        status="open",
        submitted_by=user_id,
    )
    db.add(dispute)
    statement.status = "DISPUTED"
    db.commit()
    db.refresh(dispute)
    return ProviderDisputeOut.model_validate(dispute)


# ── PA.3.6 — Sprint 9.1 — cross-tenant team performance ─────────────


@router.get(
    "/team-performance", response_model=list[ProviderMemberPerformance]
)
async def get_team_performance(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    period_days: int = Query(PERFORMANCE_DEFAULT_DAYS, ge=1, le=365),
) -> list[ProviderMemberPerformance]:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)
    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    # All members of this provider (across all tenants they serve)
    member_rows = db.execute(
        select(UserAccount, UserTenantMembership.role, UserTenantMembership.tenant_id)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(UserTenantMembership.provider_id == provider_id)
    ).all()
    if not member_rows:
        return []

    # Group memberships by user (a provider member can serve multiple tenants)
    user_meta: dict[int, tuple[UserAccount, str, list[int]]] = {}
    for u, role, tid in member_rows:
        existing = user_meta.get(u.id)
        if existing is None:
            user_meta[u.id] = (u, role, [tid])
        else:
            existing[2].append(tid)

    user_ids = list(user_meta.keys())

    # Calls (in window) by caller across tenants
    call_rows = db.execute(
        select(
            CallRecord.caller_user_id,
            func.count().label("total"),
            func.sum(case((CallRecord.billable_duration > 0, 1), else_=0)).label("connected"),
        )
        .where(CallRecord.caller_user_id.in_(user_ids))
        .where(CallRecord.created_at >= cutoff)
        .group_by(CallRecord.caller_user_id)
    ).all()
    calls_by_user: dict[int, tuple[int, int]] = {
        r.caller_user_id: (int(r.total or 0), int(r.connected or 0)) for r in call_rows
    }

    # Promised cases assigned to these users
    promised_rows = db.execute(
        select(CollectionCase.assigned_to, func.count())
        .where(CollectionCase.assigned_to.in_(user_ids))
        .where(CollectionCase.stage == "promised")
        .group_by(CollectionCase.assigned_to)
    ).all()
    promised_by_user: dict[int, int] = {r[0]: int(r[1]) for r in promised_rows}

    # Paid amount by user
    paid_rows = db.execute(
        select(CollectionCase.assigned_to, func.coalesce(func.sum(CollectionCase.amount_owed), 0))
        .where(CollectionCase.assigned_to.in_(user_ids))
        .where(CollectionCase.stage == "paid")
        .group_by(CollectionCase.assigned_to)
    ).all()
    paid_by_user: dict[int, Decimal] = {r[0]: Decimal(str(r[1])) for r in paid_rows}

    out: list[ProviderMemberPerformance] = []
    for uid, (u, role, _tids) in user_meta.items():
        total, connected = calls_by_user.get(uid, (0, 0))
        promised = promised_by_user.get(uid, 0)
        out.append(
            ProviderMemberPerformance(
                user_id=u.id,
                name=u.name,
                role=role,
                total_calls=total,
                connected_calls=connected,
                promised_cases=promised,
                conversion_rate=(promised / total) if total else None,
                paid_amount=paid_by_user.get(uid, Decimal("0")),
            )
        )
    out.sort(key=lambda x: x.total_calls, reverse=True)
    return out


# ── PA.3.7 — Sprint 9.2 — single-member commission breakdown ────────


@router.get(
    "/team/{member_user_id}/commission",
    response_model=ProviderMemberCommission,
)
async def get_member_commission(
    member_user_id: int,
    year_month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderMemberCommission:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # Verify member belongs to this provider
    row = db.execute(
        select(UserAccount)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == member_user_id,
            UserTenantMembership.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "团队成员不存在"},
        )
    member = row[0]

    year, month = (int(p) for p in year_month.split("-"))
    period_start = datetime(year, month, 1, tzinfo=UTC)
    period_end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )

    # Settled cases assigned to this user, paid in target month
    case_rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.assigned_to == member_user_id)
        .where(CollectionCase.stage == "paid")
        .where(CollectionCase.updated_at >= period_start)
        .where(CollectionCase.updated_at < period_end)
    ).all()

    items = [
        CommissionLineItem(
            case_id=c.id,
            owner_name=o.name,
            paid_amount=Decimal(str(c.amount_owed or 0)),
            paid_at=c.updated_at,
        )
        for c, o in case_rows
    ]
    base = sum((i.paid_amount for i in items), Decimal("0"))
    rate = DEFAULT_COMMISSION_RATE
    commission = (base * Decimal(str(rate))).quantize(Decimal("0.01"))

    return ProviderMemberCommission(
        user_id=member.id,
        name=member.name,
        year_month=year_month,
        commission_rate=rate,
        base_amount=base,
        commission=commission,
        items=items,
    )
