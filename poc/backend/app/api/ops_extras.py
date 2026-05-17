"""Sprint 10 — Platform ops extras (PRD §1.x / L1999-L2002).

Endpoints:
  GET   /ops/settlements/overview           — 全平台结算总览
  POST  /ops/customer-followups             — 创建跟进记录
  GET   /ops/customer-followups             — 列表（按 tenant_id 可筛）
  POST  /ops/announcements                  — 创建系统公告
  GET   /ops/announcements                  — 列表
  PATCH /ops/announcements/{id}             — 编辑公告
  DELETE /ops/announcements/{id}            — 删除公告
  GET   /ops/audit-logs/me                  — 自己的操作日志
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.audit import AuditLog
from app.models.platform import CustomerFollowup, SystemAnnouncement
from app.models.settlement import SettlementStatement
from app.models.tenant import ProviderTenantContract, Tenant
from app.models.user import UserAccount
from app.schemas.audit import AuditLogOut
from app.schemas.common import PaginatedResponse
from app.schemas.platform import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementPatchIn,
    CustomerFollowupIn,
    CustomerFollowupOut,
    SettlementOverviewOut,
    SettlementSummaryItem,
)

router = APIRouter()

OPS_ROLES = ("ops", "superadmin")


def _user_id(payload: dict) -> int:
    uid = payload.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token missing user_id"},
        )
    return int(uid)


# ── L1999 settlement overview ───────────────────────────────────────


@router.get("/settlements/overview", response_model=SettlementOverviewOut)
async def settlements_overview(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
) -> SettlementOverviewOut:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pending = db.execute(
        select(func.coalesce(func.sum(SettlementStatement.total_amount), 0)).where(
            SettlementStatement.status.in_(("DRAFT", "CONFIRMED", "DISPUTED"))
        )
    ).scalar_one() or Decimal("0")

    paid_month = db.execute(
        select(func.coalesce(func.sum(SettlementStatement.total_amount), 0))
        .where(SettlementStatement.status == "PAID")
        .where(SettlementStatement.paid_at >= month_start)
    ).scalar_one() or Decimal("0")

    overdue_count = (
        db.execute(
            select(func.count())
            .select_from(SettlementStatement)
            .where(SettlementStatement.status.in_(("DRAFT", "CONFIRMED", "DISPUTED")))
            .where(SettlementStatement.period_end < now)
        ).scalar_one()
        or 0
    )

    rows = db.execute(
        select(SettlementStatement, Tenant)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .order_by(SettlementStatement.period_end.desc())
        .limit(limit)
    ).all()

    items: list[SettlementSummaryItem] = []
    for s, t in rows:
        overdue_days = (now - s.period_end).days if s.status != "PAID" and s.period_end < now else 0
        items.append(
            SettlementSummaryItem(
                tenant_id=t.id,
                tenant_name=t.name,
                period_start=s.period_start,
                period_end=s.period_end,
                total_amount=Decimal(str(s.total_amount)),
                status=s.status,
                overdue_days=overdue_days,
            )
        )
    return SettlementOverviewOut(
        total_pending=Decimal(str(pending)),
        total_paid_month=Decimal(str(paid_month)),
        overdue_count=int(overdue_count),
        items=items,
    )


# ── L2000 customer followups ────────────────────────────────────────


def _followup_to_out(f: CustomerFollowup, tenant_name: str | None = None) -> CustomerFollowupOut:
    return CustomerFollowupOut(
        id=f.id,
        tenant_id=f.tenant_id,
        tenant_name=tenant_name,
        note=f.note,
        follow_up_at=f.follow_up_at,
        created_by=f.created_by,
        created_at=f.created_at,
    )


@router.post(
    "/customer-followups",
    response_model=CustomerFollowupOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_followup(
    body: CustomerFollowupIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerFollowupOut:
    user_id = _user_id(payload)
    tenant = db.get(Tenant, body.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    f = CustomerFollowup(
        tenant_id=body.tenant_id,
        note=body.note,
        follow_up_at=body.follow_up_at,
        created_by=user_id,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return _followup_to_out(f, tenant.name)


@router.get("/customer-followups", response_model=list[CustomerFollowupOut])
async def list_followups(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
) -> list[CustomerFollowupOut]:
    stmt = select(CustomerFollowup, Tenant.name).join(
        Tenant, Tenant.id == CustomerFollowup.tenant_id
    )
    if tenant_id:
        stmt = stmt.where(CustomerFollowup.tenant_id == tenant_id)
    rows = db.execute(stmt.order_by(CustomerFollowup.id.desc()).limit(limit)).all()
    return [_followup_to_out(f, name) for f, name in rows]


# ── L2001 system announcements ──────────────────────────────────────


@router.post(
    "/announcements",
    response_model=AnnouncementOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_announcement(
    body: AnnouncementIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AnnouncementOut:
    user_id = _user_id(payload)
    a = SystemAnnouncement(
        title=body.title,
        body=body.body,
        audience=body.audience,
        publish_at=body.publish_at,
        created_by=user_id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return AnnouncementOut.model_validate(a)


@router.get("/announcements", response_model=list[AnnouncementOut])
async def list_announcements(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    state: str | None = Query(None, pattern=r"^(draft|published|scheduled)$"),
    limit: int = Query(100, ge=1, le=500),
) -> list[AnnouncementOut]:
    stmt = select(SystemAnnouncement)
    now = datetime.now(UTC)
    if state == "draft":
        stmt = stmt.where(SystemAnnouncement.publish_at.is_(None))
    elif state == "published":
        stmt = stmt.where(SystemAnnouncement.publish_at <= now)
    elif state == "scheduled":
        stmt = stmt.where(SystemAnnouncement.publish_at > now)
    rows = db.execute(stmt.order_by(SystemAnnouncement.id.desc()).limit(limit)).scalars().all()
    return [AnnouncementOut.model_validate(a) for a in rows]


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
async def patch_announcement(
    announcement_id: int,
    body: AnnouncementPatchIn,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AnnouncementOut:
    a = db.get(SystemAnnouncement, announcement_id)
    if a is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "公告不存在"},
        )
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(a, field, value)
    db.commit()
    db.refresh(a)
    return AnnouncementOut.model_validate(a)


@router.delete(
    "/announcements/{announcement_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_announcement(
    announcement_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    a = db.get(SystemAnnouncement, announcement_id)
    if a is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "公告不存在"},
        )
    db.delete(a)
    db.commit()


# ── L2002 my own audit log (filtered, no global access) ─────────────


@router.get("/audit-logs/me", response_model=PaginatedResponse[AuditLogOut])
async def my_audit_logs(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogOut]:
    user_id = _user_id(payload)
    stmt = select(AuditLog).where(AuditLog.actor_user_id == user_id)
    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
