"""Sprint 14.2 / 15.2 — 实时通话墙数据源 + 干预 (PRD §11.6 / §13)。

GET  /api/v1/supervisor/live-calls
  返回当前租户内 status IN ('dialing','live') 的全部通话快照。
  WS /ws/supervisor 推增量；本端点用于页面初次加载。

POST /api/v1/supervisor/calls/{call_id}/force-hangup
  督导手动结束某通话；走 call_intervention.dispatch_force_hangup。
  权限：supervisor / admin / project_manager
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.call import LiveCallItem, LiveCallsOut

from ._supervisor_scope import SupervisorScope, supervisor_case_filter, supervisor_scope

router = APIRouter()

WALL_ROLES = ("supervisor", "admin", "project_manager")


def _allowed_case_clause(scope: SupervisorScope) -> sa.ColumnElement[bool]:
    """CallRecord 的 case 是否落在督导 scope 内。

    服务商督导：case 必须属本服务商项目（无 case 的通话不可见——无归属）。
    物业督导：case 属物业 / 无项目，或通话本身无 case_id（保留既有「物业看本租户全部」语义）。
    """
    allowed_case_ids = select(CollectionCase.id).where(supervisor_case_filter(scope))
    clause = CallRecord.case_id.in_(allowed_case_ids)
    if scope.provider_id is None:
        clause = sa.or_(CallRecord.case_id.is_(None), clause)
    return clause


class ForceHangupReq(BaseModel):
    reason: str  # 督导填写原因，存入 audit


class ForceHangupResp(BaseModel):
    call_id: int
    triggered_by: str
    reason: str


class TakeoverReq(BaseModel):
    reason: str  # 主管填写原因


class TakeoverResp(BaseModel):
    call_id: int
    status: str  # "requested"
    supervisor_name: str
    reason: str


@router.get("/live-calls", response_model=LiveCallsOut)
def list_live_calls(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*WALL_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> LiveCallsOut:
    rows = (
        db.execute(
            select(CallRecord)
            .where(
                CallRecord.tenant_id == scope.tenant_id,
                CallRecord.status.in_(("dialing", "live")),
                _allowed_case_clause(scope),
            )
            .order_by(CallRecord.started_at.desc().nulls_last())
        )
        .scalars()
        .all()
    )

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, scope.tenant_id, scope.provider_id)
    owner_phone_reveal = should_reveal_owner_phone(role=role, provider_id=scope.provider_id, contract_active=contract_active)

    now = datetime.now(UTC)
    items: list[LiveCallItem] = []
    for c in rows:
        caller = db.get(UserAccount, c.caller_user_id) if c.caller_user_id else None
        case = db.get(CollectionCase, c.case_id) if c.case_id else None
        owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
        duration = 0
        if c.started_at:
            duration = max(0, int((now - c.started_at).total_seconds()))
        items.append(
            LiveCallItem(
                call_id=c.id,
                case_id=c.case_id,
                caller_user_id=c.caller_user_id,
                caller_name=caller.name if caller else "未知坐席",
                owner_name=owner.name if owner else None,
                owner_phone_masked=display_owner_phone(
                    owner.phone_enc if owner else None,
                    reveal=owner_phone_reveal,
                ),
                started_at=c.started_at,
                last_heartbeat_at=c.last_heartbeat_at,
                duration_sec=duration,
                recording_mode=c.recording_mode,
                status=c.status,
                risk_flagged=bool(c.risk_flagged),
            )
        )
    return LiveCallsOut(items=items)


@router.post("/calls/{call_id}/force-hangup", response_model=ForceHangupResp)
async def supervisor_force_hangup(
    call_id: int,
    body: ForceHangupReq,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*WALL_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> ForceHangupResp:
    """督导手动结束某通话 (Sprint 15.2 / 15.3)。"""
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == scope.tenant_id,
            _allowed_case_clause(scope),
        )
    ).scalar_one_or_none()
    if call is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话不存在或不在督导范围内"},
        )
    if call.status not in ("dialing", "live"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_CALL_NOT_ACTIVE", "message": f"通话状态 {call.status} 无法结束"},
        )

    from app.services.call_intervention import dispatch_force_hangup

    await dispatch_force_hangup(
        db,
        call_id=call.id,
        tenant_id=scope.tenant_id,
        reason=body.reason,
        triggered_by="supervisor.manual",
        supervisor_user_id=user_id,
    )

    return ForceHangupResp(
        call_id=call.id,
        triggered_by="supervisor.manual",
        reason=body.reason,
    )


@router.post("/calls/{call_id}/takeover", response_model=TakeoverResp)
async def supervisor_takeover(
    call_id: int,
    body: TakeoverReq,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*WALL_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> TakeoverResp:
    """督导发起强制转接请求 (Sprint 15.3, PRD §11.2)。

    后续动作：agent App 收到 supervisor.takeover_request → 弹层选择
    accept/reject → POST /calls/{call_id}/takeover-response 回应。
    """
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == scope.tenant_id,
            _allowed_case_clause(scope),
        )
    ).scalar_one_or_none()
    if call is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话不存在或不在督导范围内"},
        )
    if call.status not in ("dialing", "live"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_CALL_NOT_ACTIVE", "message": f"通话状态 {call.status} 不可转接"},
        )

    supervisor = db.get(UserAccount, user_id)
    supervisor_name = supervisor.name if supervisor else "未知主管"

    from app.services.call_intervention import dispatch_takeover_request

    await dispatch_takeover_request(
        db,
        call_id=call.id,
        tenant_id=scope.tenant_id,
        supervisor_user_id=user_id,
        supervisor_name=supervisor_name,
        reason=body.reason,
    )
    return TakeoverResp(
        call_id=call.id,
        status="requested",
        supervisor_name=supervisor_name,
        reason=body.reason,
    )
