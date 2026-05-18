"""v1.6 — 督导值班排班 API（DB 持久化）。

GET    /api/v1/supervisor/shifts                     列出本租户下周排班
POST   /api/v1/supervisor/shifts                     组长批量保存（仅 is_shift_lead 用户）
POST   /api/v1/supervisor/shifts/swap-request        普通督导发起调班申请
GET    /api/v1/supervisor/shifts/swap-requests       本租户调班申请列表

组长由 user_account.preferences.is_shift_lead = true 标识（JSONB 字段，无需新表）。
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._supervisor_scope import SupervisorScope, supervisor_scope
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles, require_tenant_roles
from app.models.supervisor_shift import SupervisorShift, SupervisorShiftSwapRequest
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor",)
SLOTS = ("morning", "afternoon", "evening")


def _shift_scope_clause(
    scope: SupervisorScope,
    model: type[SupervisorShift] | type[SupervisorShiftSwapRequest],
) -> sa.ColumnElement[bool]:
    """SupervisorShift / SupervisorShiftSwapRequest 的 scope 过滤（自含 tenant_id）。

    物业侧 scope（provider_id=None）→ provider_id IS NULL；
    服务商侧 scope → provider_id == 本服务商。
    """
    if scope.provider_id is None:
        provider_cond = model.provider_id.is_(None)
    else:
        provider_cond = model.provider_id == scope.provider_id
    return sa.and_(model.tenant_id == scope.tenant_id, provider_cond)


def _is_shift_lead(user: UserAccount | None) -> bool:
    if user is None:
        return False
    prefs = user.preferences or {}
    return bool(prefs.get("is_shift_lead", False))


def _ensure_seed_week(db: Session, scope: SupervisorScope) -> None:
    """若本 scope 本周未排班，给 7 天每个时段插入空记录（占位），让前端可编辑。"""
    today = date_type.today()
    end = today + timedelta(days=6)
    existing = db.execute(
        select(SupervisorShift.shift_date, SupervisorShift.slot)
        .where(_shift_scope_clause(scope, SupervisorShift))
        .where(SupervisorShift.shift_date.between(today, end))
    ).all()
    have = {(r[0], r[1]) for r in existing}
    inserts = []
    for i in range(7):
        d = today + timedelta(days=i)
        for s in SLOTS:
            if (d, s) not in have:
                inserts.append(
                    SupervisorShift(
                        tenant_id=scope.tenant_id,
                        provider_id=scope.provider_id,
                        shift_date=d,
                        slot=s,
                        supervisor_user_id=None,
                        supervisor_name="",
                    )
                )
    if inserts:
        db.add_all(inserts)
        db.commit()


@router.get("/shifts")
async def list_shifts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    is_lead = _is_shift_lead(user)

    _ensure_seed_week(db, scope)

    today = date_type.today()
    end = today + timedelta(days=6)
    rows = (
        db.execute(
            select(SupervisorShift)
            .where(_shift_scope_clause(scope, SupervisorShift))
            .where(SupervisorShift.shift_date.between(today, end))
            .order_by(SupervisorShift.shift_date, SupervisorShift.slot)
        )
        .scalars()
        .all()
    )

    by_date: dict[str, dict[str, str]] = {}
    for r in rows:
        ds = r.shift_date.isoformat()
        by_date.setdefault(ds, {"morning": "", "afternoon": "", "evening": ""})
        by_date[ds][r.slot] = r.supervisor_name or ""

    # 本 scope 的督导列表，给前端做下拉
    sup_q = (
        select(UserAccount.name)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(UserTenantMembership.tenant_id == scope.tenant_id)
        .where(UserTenantMembership.role == "supervisor")
        .where(UserAccount.is_active.is_(True))
        .distinct()
    )
    if scope.provider_id is None:
        sup_q = sup_q.where(UserTenantMembership.provider_id.is_(None))
    else:
        sup_q = sup_q.where(UserTenantMembership.provider_id == scope.provider_id)
    supervisors = [r[0] for r in db.execute(sup_q).all()]
    if user and user.name not in supervisors:
        supervisors.append(user.name)

    return {
        "tenant_id": scope.tenant_id,
        "is_shift_lead": is_lead,
        "current_user_name": user.name if user else "",
        "supervisors": supervisors,
        "shifts": [{"date": d, **slots} for d, slots in sorted(by_date.items())],
    }


@router.post("/shifts")
async def save_shifts(
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"shifts": [{"date": "2026-05-08", "morning": "...", "afternoon": "...", "evening": "..."}]}"""
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "督导必须关联租户"},
        )
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    if not _is_shift_lead(user):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NOT_SHIFT_LEAD",
                "message": "仅排班负责人可编辑全员排班；如需调班请走 swap-request",
            },
        )
    raw = body.get("shifts")
    if not isinstance(raw, list):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "shifts 必须为数组"},
        )

    saved = 0
    for s in raw:
        d_str = s.get("date")
        if not isinstance(d_str, str):
            continue
        try:
            d = date_type.fromisoformat(d_str)
        except ValueError:
            continue
        for slot in SLOTS:
            name = s.get(slot, "") or ""
            row = db.execute(
                select(SupervisorShift)
                .where(SupervisorShift.tenant_id == int(tenant_id))
                .where(SupervisorShift.shift_date == d)
                .where(SupervisorShift.slot == slot)
            ).scalar_one_or_none()
            if row is None:
                row = SupervisorShift(
                    tenant_id=int(tenant_id),
                    shift_date=d,
                    slot=slot,
                    supervisor_name=name,
                )
                db.add(row)
            else:
                row.supervisor_name = name
            saved += 1
    db.commit()
    return {"saved": saved}


@router.post("/shifts/swap-request")
async def submit_swap_request(
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"date": "...", "slot": "...", "swap_with": "督导张敏"}"""
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "督导必须关联租户"},
        )
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    d_str = body.get("date")
    slot = body.get("slot")
    swap_with = body.get("swap_with")
    if slot not in SLOTS or not isinstance(d_str, str) or not isinstance(swap_with, str):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "date / slot / swap_with 必填"},
        )
    try:
        d = date_type.fromisoformat(d_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "date 格式无效"},
        ) from exc

    row = db.execute(
        select(SupervisorShift)
        .where(SupervisorShift.tenant_id == int(tenant_id))
        .where(SupervisorShift.shift_date == d)
        .where(SupervisorShift.slot == slot)
    ).scalar_one_or_none()
    if not user or not row or row.supervisor_name != user.name:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_OWN_SLOT", "message": "只能对自己已排的班次发起调班"},
        )

    req = SupervisorShiftSwapRequest(
        tenant_id=int(tenant_id),
        from_user_id=user_id,
        from_user_name=user.name,
        to_user_name=swap_with,
        shift_date=d,
        slot=slot,
        status="pending_confirm",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "id": req.id,
        "tenant_id": req.tenant_id,
        "from_user": req.from_user_name,
        "to_user": req.to_user_name,
        "date": req.shift_date.isoformat(),
        "slot": req.slot,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.get("/shifts/swap-requests")
async def list_swap_requests(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        return []
    rows = (
        db.execute(
            select(SupervisorShiftSwapRequest)
            .where(SupervisorShiftSwapRequest.tenant_id == int(tenant_id))
            .order_by(SupervisorShiftSwapRequest.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "from_user": r.from_user_name,
            "to_user": r.to_user_name,
            "date": r.shift_date.isoformat(),
            "slot": r.slot,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
