"""Sprint 10 — Admin Settlement Management router.

GET    /api/v1/admin/settlements                      list (PaginatedResponse[SettlementOut])
GET    /api/v1/admin/settlements/{id}                 detail (SettlementDetailOut with disputes)
PATCH  /api/v1/admin/settlements/{id}/confirm         DRAFT → CONFIRMED
PATCH  /api/v1/admin/settlements/{id}/pay             CONFIRMED → PAID (+payment_proof_url)
POST   /api/v1/admin/settlements/{id}/dispute         any non-PAID → DISPUTED + DisputeRecord
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.settlement import DisputeRecord, SettlementStatement
from app.models.tenant import ProviderTenantContract, ServiceProvider
from app.schemas.common import PaginatedResponse
from app.schemas.settlement import (
    DisputeIn,
    DisputeOut,
    PayIn,
    SettlementDetailOut,
    SettlementOut,
)
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _statement_to_out(
    s: SettlementStatement,
    provider: ServiceProvider | None,
) -> SettlementOut:
    return SettlementOut(
        id=s.id,
        contract_id=s.contract_id,
        provider_id=provider.id if provider else None,
        provider_name=provider.name if provider else None,
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


def _load_statement_for_tenant(
    db: Session, statement_id: int, tenant_id: int
) -> tuple[SettlementStatement, ProviderTenantContract, ServiceProvider]:
    """Load a settlement + its contract + provider, scoped by tenant_id.

    Returns 404 if not found or belongs to another tenant.
    """
    row = db.execute(
        select(SettlementStatement, ProviderTenantContract, ServiceProvider)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .join(
            ServiceProvider,
            ServiceProvider.id == ProviderTenantContract.provider_id,
        )
        .where(
            SettlementStatement.id == statement_id,
            ProviderTenantContract.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "结算单不存在"},
        )
    return row[0], row[1], row[2]


def _invalid_transition() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_409_CONFLICT,
        detail={
            "code": "ERR_INVALID_TRANSITION",
            "message": "当前状态不允许此操作",
        },
    )


@router.get("/settlements", response_model=PaginatedResponse[SettlementOut])
def list_settlements(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, description="DRAFT/CONFIRMED/PAID/DISPUTED"),
    year_month: str | None = Query(None, description="YYYY-MM, filters by period_start"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[SettlementOut]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(SettlementStatement, ProviderTenantContract, ServiceProvider)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .join(
            ServiceProvider,
            ServiceProvider.id == ProviderTenantContract.provider_id,
        )
        .where(ProviderTenantContract.tenant_id == tenant_id)
    )

    if status:
        stmt = stmt.where(SettlementStatement.status == status)

    if year_month:
        # Filter by year-month of period_start: YYYY-MM
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

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(
            SettlementStatement.period_start.desc(),
            SettlementStatement.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_statement_to_out(s, p) for s, _c, p in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/settlements/{statement_id}", response_model=SettlementDetailOut)
def get_settlement(
    statement_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SettlementDetailOut:
    tenant_id = _require_tenant(payload)
    s, _contract, provider = _load_statement_for_tenant(db, statement_id, tenant_id)

    disputes = (
        db.execute(
            select(DisputeRecord)
            .where(DisputeRecord.statement_id == statement_id)
            .order_by(DisputeRecord.id.desc())
        )
        .scalars()
        .all()
    )

    base = _statement_to_out(s, provider)
    return SettlementDetailOut(
        **base.model_dump(),
        disputes=[DisputeOut.model_validate(d) for d in disputes],
    )


@router.patch("/settlements/{statement_id}/confirm", response_model=SettlementOut)
def confirm_settlement(
    statement_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SettlementOut:
    tenant_id = _require_tenant(payload)
    s, _contract, provider = _load_statement_for_tenant(db, statement_id, tenant_id)

    if s.status != "DRAFT":
        raise _invalid_transition()

    s.status = "CONFIRMED"
    s.confirmed_at = datetime.now(UTC)
    db.commit()
    db.refresh(s)
    return _statement_to_out(s, provider)


@router.patch("/settlements/{statement_id}/pay", response_model=SettlementOut)
def pay_settlement(
    statement_id: int,
    body: PayIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SettlementOut:
    tenant_id = _require_tenant(payload)
    s, _contract, provider = _load_statement_for_tenant(db, statement_id, tenant_id)

    if s.status != "CONFIRMED":
        raise _invalid_transition()

    s.status = "PAID"
    s.paid_at = datetime.now(UTC)
    if body.payment_proof_url is not None:
        s.payment_proof_url = body.payment_proof_url
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="settlement.pay",
        target_type="settlement",
        target_id=s.id,
        payload={
            "amount": str(s.total_amount) if s.total_amount is not None else None,
            "proof_url": body.payment_proof_url,
        },
    )
    db.commit()
    db.refresh(s)
    return _statement_to_out(s, provider)


@router.post(
    "/settlements/{statement_id}/dispute",
    response_model=DisputeOut,
    status_code=http_status.HTTP_201_CREATED,
)
def raise_dispute(
    statement_id: int,
    body: DisputeIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DisputeOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    s, _contract, _provider = _load_statement_for_tenant(db, statement_id, tenant_id)

    # Cannot dispute an already-paid statement
    if s.status == "PAID":
        raise _invalid_transition()

    record = DisputeRecord(
        statement_id=statement_id,
        reason=body.reason,
        status="open",
        submitted_by=user_id,
    )
    db.add(record)
    s.status = "DISPUTED"
    db.commit()
    db.refresh(record)
    return DisputeOut.model_validate(record)
