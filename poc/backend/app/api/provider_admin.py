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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_password_hash, get_token_payload, require_provider_roles


def _gen_random_password() -> str:
    """v0.7.0 — 生成一次性随机密码(16 位 alphanumeric)。员工首次 OTP 登录后改。"""
    import secrets
    import string

    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(16))
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
    ProjectCommissionRateIn,
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

PROVIDER_ROLES = (
    "admin",
)  # provider-side admin; guarded by provider_id != None in _resolve_provider_id
PROVIDER_PM_ROLES = ("project_manager", "admin")  # §9.2-D2 — PM 也可改项目佣金率


# ── helpers ──────────────────────────────────────────────────────────


def _resolve_provider_id(user_id: int, db: Session) -> int:
    """Find the provider_id linked to a provider_admin user.

    Returns 404 ERR_NO_PROVIDER if the user has no membership row with
    a non-null provider_id (account misconfigured).
    """
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
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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
    partner_tenant_count: int = (
        db.execute(
            select(func.count(func.distinct(ProviderTenantContract.tenant_id))).where(
                ProviderTenantContract.provider_id == provider_id
            )
        ).scalar_one()
        or 0
    )

    # 团队人数 — active memberships under this provider
    team_count: int = (
        db.execute(
            select(func.count(UserTenantMembership.id)).where(
                UserTenantMembership.provider_id == provider_id
            )
        ).scalar_one()
        or 0
    )

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
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

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
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


# ── PA.3.3 team management ──────────────────────────────────────────


@router.post(
    "/team",
    response_model=ProviderTeamMemberOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_team_member(
    body: TeamMemberCreateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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

    # v0.7.0 — password 可选,缺省时生成随机一次性密码;员工首次走 OTP 登录
    raw_password = body.password or _gen_random_password()
    new_user = UserAccount(
        phone_enc=encrypt_phone(body.phone),
        name=body.name,
        password_hash=get_password_hash(raw_password),
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
        provider_id=provider_id,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)
    return _team_member_to_out(new_user, body.role, True)


@router.get("/team", response_model=PaginatedResponse[ProviderTeamMemberOut])
async def list_team_members(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = db.execute(
        stmt.order_by(UserAccount.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [_team_member_to_out(user, role, m_active) for user, role, m_active in rows]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/team/{member_user_id}", response_model=ProviderTeamMemberDetailOut)
async def get_team_member(
    member_user_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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


@router.get("/settlements", response_model=PaginatedResponse[ProviderSettlementOut])
async def list_provider_settlements(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, description="DRAFT/CONFIRMED/PAID/DISPUTED"),
    year_month: str | None = Query(None, description="YYYY-MM, filters by period_start"),
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

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = db.execute(
        stmt.order_by(
            SettlementStatement.period_start.desc(),
            SettlementStatement.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [_settlement_to_out(s, c, t) for s, c, t in rows]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/settlements/{statement_id}",
    response_model=ProviderSettlementDetailOut,
)
async def get_provider_settlement(
    statement_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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

    disputes = (
        db.execute(
            select(DisputeRecord)
            .where(DisputeRecord.statement_id == statement_id)
            .order_by(DisputeRecord.id.desc())
        )
        .scalars()
        .all()
    )

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
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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


@router.get("/team-performance", response_model=list[ProviderMemberPerformance])
async def get_team_performance(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
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
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderMemberCommission:
    """§9.2-C/D2 — 服务商单成员当月佣金。

    逐案件：实收（扣已执行减免）× 该案项目的 provider_agent_commission_rate
    （NULL 回退系统默认 0.05），求和。commission_rate 透出加权有效率。
    服务商成员可跨租户接案，故按 tenant_id 分组取减免后合并。
    """
    from collections import defaultdict

    from app.models.case import Project
    from app.services.commission import executed_discount_amounts, provider_agent_rate

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

    # 服务商成员可跨租户接案 —— 按 tenant_id 分组取已执行减免后合并（case_id 全局唯一）
    ids_by_tenant: dict[int, list[int]] = defaultdict(list)
    for c, _o in case_rows:
        ids_by_tenant[c.tenant_id].append(c.id)
    executed: dict[int, Decimal] = {}
    for tid, ids in ids_by_tenant.items():
        executed.update(executed_discount_amounts(db, tid, ids))

    project_cache: dict[int, Project | None] = {}

    def _project(project_id: int | None) -> Project | None:
        if project_id is None:
            return None
        if project_id not in project_cache:
            project_cache[project_id] = db.get(Project, project_id)
        return project_cache[project_id]

    items: list[CommissionLineItem] = []
    base = Decimal("0")
    commission = Decimal("0")
    for c, o in case_rows:
        collected = executed[c.id] if c.id in executed else Decimal(str(c.amount_owed or 0))
        rate = provider_agent_rate(_project(c.project_id))
        base += collected
        commission += (collected * rate).quantize(Decimal("0.01"))
        items.append(
            CommissionLineItem(
                case_id=c.id,
                owner_name=o.name,
                paid_amount=collected,
                paid_at=c.updated_at,
                commission_rate=rate,
            )
        )
    effective_rate = float(commission / base) if base > 0 else DEFAULT_COMMISSION_RATE

    return ProviderMemberCommission(
        user_id=member.id,
        name=member.name,
        year_month=year_month,
        commission_rate=effective_rate,
        base_amount=base,
        commission=commission,
        items=items,
    )


# ── v1.5.5: 项目时效相关 ─────────────────────────────────────────


@router.get("/projects/expiring")
async def list_expiring_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.5.5 — 服务商端总览 banner 用：30 天内即将到期的项目计数 + 列表。"""
    from app.models.case import Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)
    horizon = datetime.now(UTC) + timedelta(days=30)
    rows = db.execute(
        select(Project.id, Project.name, Project.plan_end)
        .where(
            Project.provider_id == provider_id,
            Project.status == "active",
            Project.plan_end.is_not(None),
            Project.plan_end >= datetime.now(UTC),
            Project.plan_end <= horizon,
        )
        .order_by(Project.plan_end.asc())
    ).all()
    return {
        "count": len(rows),
        "items": [
            {"id": r[0], "name": r[1], "plan_end": r[2].isoformat() if r[2] else None} for r in rows
        ],
    }


@router.get("/historical-reports")
async def list_historical_reports(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.5.5 D2 — 到期 30 天内的项目聚合报表（仅展示数字、不可下钻）。"""
    from app.models.case import CollectionCase, Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # 仅展示已 closed 且 30 天内的项目（active 已在主入口可见）
    cutoff = datetime.now(UTC) - timedelta(days=30)
    rows = (
        db.execute(
            select(Project)
            .where(
                Project.provider_id == provider_id,
                Project.status == "closed",
                Project.updated_at >= cutoff,
            )
            .order_by(Project.updated_at.desc())
        )
        .scalars()
        .all()
    )

    items = []
    for p in rows:
        # 聚合：案件数 / 总欠费 / 已回款金额
        agg = db.execute(
            select(
                func.count(CollectionCase.id),
                func.coalesce(func.sum(CollectionCase.amount_owed), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (CollectionCase.stage == "paid", CollectionCase.amount_owed),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(
                CollectionCase.project_id == p.id,
                CollectionCase.tenant_id == p.tenant_id,
            )
        ).one()
        items.append(
            {
                "project_id": p.id,
                "project_name": p.name,
                "plan_start": p.plan_start.isoformat() if p.plan_start else None,
                "plan_end": p.plan_end.isoformat() if p.plan_end else None,
                "closed_at": p.updated_at.isoformat(),
                "case_count": int(agg[0] or 0),
                "total_owed": float(agg[1] or 0),
                "total_recovered": float(agg[2] or 0),
            }
        )
    return {"items": items, "retention_days": 30}


# ── v1.5.6: 服务商端项目列表 + 指派 PM ───────────────────────────


@router.get("/projects")
async def list_provider_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.5.6 — 服务商工作台「我的项目」列表（仅 active + 服务期未过）。"""
    from app.core.provider_scope import active_project_filter
    from app.models.case import Project
    from app.models.tenant import Tenant

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    rows = db.execute(
        select(Project, Tenant.name)
        .join(Tenant, Tenant.id == Project.tenant_id)
        .where(*active_project_filter(provider_id))
        .order_by(Project.id.desc())
    ).all()

    items = []
    for p, tname in rows:
        # 解析当前 PM 名字（若已指派）
        pm_name: str | None = None
        if p.provider_pm_user_id is not None:
            pm_name = db.execute(
                select(UserAccount.name).where(UserAccount.id == p.provider_pm_user_id)
            ).scalar_one_or_none()
        items.append(
            {
                "project_id": p.id,
                "project_name": p.name,
                "tenant_name": tname,
                "plan_start": p.plan_start.isoformat() if p.plan_start else None,
                "plan_end": p.plan_end.isoformat() if p.plan_end else None,
                "provider_pm_user_id": p.provider_pm_user_id,
                "provider_pm_name": pm_name,
                "provider_agent_commission_rate": (
                    str(p.provider_agent_commission_rate)
                    if p.provider_agent_commission_rate is not None
                    else None
                ),
            }
        )
    return {"items": items}


class AssignProviderPmIn(BaseModel):
    user_id: int


@router.patch("/projects/{project_id}/pm")
async def assign_provider_pm(
    project_id: int,
    body: AssignProviderPmIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.5.6 — 服务商 admin 指派本家项目经理给项目。"""
    from app.models.case import Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.provider_id == provider_id,
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在或不属本服务商"},
        )

    # 校验 user_id 是本服务商的 project_manager 角色（provider_id 已限定服务商侧）
    pm_membership = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == body.user_id,
            UserTenantMembership.provider_id == provider_id,
            UserTenantMembership.role == "project_manager",
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if pm_membership is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_NOT_PM",
                "message": "指定用户不是本服务商的项目经理",
            },
        )

    project.provider_pm_user_id = body.user_id
    db.commit()
    return {"status": "ok", "project_id": project.id, "pm_user_id": body.user_id}


@router.patch("/projects/{project_id}/commission-rate")
async def set_project_commission_rate(
    project_id: int,
    body: ProjectCommissionRateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_PM_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """§9.2-D2 — 服务商 PM/admin 设置本家项目的服务商催收员佣金率。"""
    from app.models.case import Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.provider_id == provider_id,
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在或不属本服务商"},
        )

    project.provider_agent_commission_rate = body.provider_agent_commission_rate
    db.commit()
    return {
        "status": "ok",
        "project_id": project.id,
        "provider_agent_commission_rate": str(body.provider_agent_commission_rate),
    }


# v0.7.0 — 服务商「我的项目」独立详情页 + 团队绩效
@router.get("/projects/{project_id}")
async def get_provider_project_detail(
    project_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """服务商「我的项目」详情(只读)— 项目卡 + 收费/合同 + KPI 3 卡。

    校验:project.provider_id == self_provider_id(确保服务商只能看自己接的项目)。
    返回字段全只读;服务商**不能**改项目本身的字段(创建/编辑由物业 admin 负责)。
    """
    from app.core.provider_scope import active_project_filter
    from app.models.case import CollectionCase, Project
    from app.models.tenant import Tenant

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(Project, Tenant.name)
        .join(Tenant, Tenant.id == Project.tenant_id)
        .where(Project.id == project_id)
        .where(Project.provider_id == provider_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_NOT_FOUND",
                "message": "项目不存在或不在本服务商范围",
            },
        )
    project, tenant_name = row

    # KPI 聚合
    case_count = db.execute(
        select(func.count(CollectionCase.id))
        .where(CollectionCase.project_id == project_id)
    ).scalar_one() or 0

    paid_count = db.execute(
        select(func.count(CollectionCase.id))
        .where(CollectionCase.project_id == project_id)
        .where(CollectionCase.stage == "paid")
    ).scalar_one() or 0

    recovered_amount = db.execute(
        select(func.coalesce(func.sum(CollectionCase.amount_owed), 0))
        .where(CollectionCase.project_id == project_id)
        .where(CollectionCase.stage == "paid")
    ).scalar() or 0

    receivable_amount = db.execute(
        select(func.coalesce(func.sum(CollectionCase.amount_owed), 0))
        .where(CollectionCase.project_id == project_id)
    ).scalar() or 0

    # 预估佣金 = recovered × provider_agent_commission_rate
    rate = project.provider_agent_commission_rate
    estimated_commission = (
        float(recovered_amount) * float(rate) if rate is not None else None
    )

    # PM 名字
    pm_name = None
    if project.provider_pm_user_id is not None:
        pm_name = db.execute(
            select(UserAccount.name).where(UserAccount.id == project.provider_pm_user_id)
        ).scalar_one_or_none()

    return {
        "project_id": project.id,
        "project_name": project.name,
        "status": project.status,
        "description": project.description,
        "tenant_name": tenant_name,
        "plan_start": project.plan_start.isoformat() if project.plan_start else None,
        "plan_end": project.plan_end.isoformat() if project.plan_end else None,
        # 收费
        "charge_rate_text": project.charge_rate_text,
        "charge_period": project.charge_period,
        "charge_notes": project.charge_notes,
        # 合同
        "contract_type": project.contract_type,
        "contract_start_date": (
            project.contract_start_date.isoformat()
            if project.contract_start_date
            else None
        ),
        "contract_end_date": (
            project.contract_end_date.isoformat()
            if project.contract_end_date
            else None
        ),
        "contract_attachment_filename": project.contract_attachment_filename,
        # 团队
        "provider_pm_user_id": project.provider_pm_user_id,
        "provider_pm_name": pm_name,
        "provider_agent_commission_rate": (
            str(project.provider_agent_commission_rate)
            if project.provider_agent_commission_rate is not None
            else None
        ),
        # KPI
        "case_count": int(case_count),
        "paid_count": int(paid_count),
        "recovered_amount": str(recovered_amount),
        "receivable_amount": str(receivable_amount),
        "estimated_commission": (
            f"{estimated_commission:.2f}" if estimated_commission is not None else None
        ),
    }


@router.get("/projects/{project_id}/team-stats")
async def get_provider_project_team_stats(
    project_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v0.7.0 — 项目详情页「团队绩效」section。
    返回本服务商在该项目接案的员工列表 + 各自 case/paid 计数。
    """
    from app.models.case import CollectionCase, Project

    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # 项目归属校验
    proj = db.execute(
        select(Project.id)
        .where(Project.id == project_id)
        .where(Project.provider_id == provider_id)
    ).scalar_one_or_none()
    if proj is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在或不在本服务商范围"},
        )

    # 按 assigned_to 分组,仅本服务商 membership
    rows = db.execute(
        select(
            CollectionCase.assigned_to,
            UserAccount.name,
            func.count(CollectionCase.id).label("case_count"),
            func.sum(
                case((CollectionCase.stage == "paid", 1), else_=0)
            ).label("paid_count"),
            func.coalesce(
                func.sum(
                    case(
                        (CollectionCase.stage == "paid", CollectionCase.amount_owed),
                        else_=0,
                    )
                ),
                0,
            ).label("recovered_amount"),
        )
        .join(UserAccount, UserAccount.id == CollectionCase.assigned_to, isouter=True)
        .join(
            UserTenantMembership,
            UserTenantMembership.user_id == CollectionCase.assigned_to,
        )
        .where(CollectionCase.project_id == project_id)
        .where(CollectionCase.assigned_to.isnot(None))
        .where(UserTenantMembership.provider_id == provider_id)
        .group_by(CollectionCase.assigned_to, UserAccount.name)
        .order_by(func.count(CollectionCase.id).desc())
    ).all()

    items = [
        {
            "user_id": r.assigned_to,
            "name": r.name or "—",
            "case_count": int(r.case_count or 0),
            "paid_count": int(r.paid_count or 0),
            "recovered_amount": str(r.recovered_amount or 0),
        }
        for r in rows
    ]
    return {"items": items}
