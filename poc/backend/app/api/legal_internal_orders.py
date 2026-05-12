"""v1.9.0 — 物业内部法务处理订单 endpoints。

法务老周（role=legal）和 admin 共用：
- GET  /legal/internal-orders                — 待处理列表（status=internal_processing）+ 已关闭
- GET  /legal/internal-orders/{id}           — 详情（含历史 actions）
- POST /legal/internal-orders/{id}/actions   — 记录一次操作（沟通/律师函/调解/...）
- POST /legal/internal-orders/{id}/close     — 关闭订单（带 close_reason → 联动 case.stage）
- POST /legal/internal-orders/{id}/escalate  — 升级到律所（仅标记 status，方案 C 才实际派单）
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import LegalConversionOrder, LegalConversionRequest
from app.models.legal_internal import (
    InternalLegalLetterTemplate,
    LegalInternalAction,
    PartnerLawFirm,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_internal import (
    LegalInternalActionCreate,
    LegalInternalActionOut,
    LegalInternalOrderCloseRequest,
    LegalInternalOrderDetailOut,
    LegalInternalOrderListItem,
)
from app.services.audit import log_audit

router = APIRouter()

LEGAL_ROLES = ("legal", "admin", "supervisor")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    return int(tenant_id)


def _action_to_out(
    a: LegalInternalAction,
    actor_name: str | None = None,
    template_name: str | None = None,
    law_firm_name: str | None = None,
) -> LegalInternalActionOut:
    return LegalInternalActionOut(
        id=a.id,
        legal_order_id=a.legal_order_id,
        case_id=a.case_id,
        action_type=a.action_type,
        actor_user_id=a.actor_user_id,
        actor_name=actor_name,
        occurred_at=a.occurred_at,
        note=a.note,
        letter_template_id=a.letter_template_id,
        letter_template_name=template_name,
        partner_law_firm_id=a.partner_law_firm_id,
        partner_law_firm_name=law_firm_name,
        attachment_key=a.attachment_key,
        attachment_filename=a.attachment_filename,
        letter_variables=a.letter_variables,
    )


def _legal_stage_for_close_reason(reason: str) -> str | None:
    """关闭法务订单后联动更新 case.stage。"""
    return {
        "paid": "paid",
        "promised": "promised",
        "uncollectible": "closed",
        "escalated": None,  # 升级律所不联动 case.stage
    }.get(reason)


# ── List ──────────────────────────────────────────────────────
@router.get(
    "/internal-orders",
    response_model=PaginatedResponse[LegalInternalOrderListItem],
)
def list_internal_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    tab: str = Query("pending", pattern="^(pending|closed|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalInternalOrderListItem]:
    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    reveal = should_reveal_owner_phone(role=role, contract_active=contract_active)

    stmt = (
        select(LegalConversionOrder, OwnerProfile)
        .join(CollectionCase, CollectionCase.id == LegalConversionOrder.case_id)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(LegalConversionOrder.tenant_id == tenant_id)
    )
    if tab == "pending":
        stmt = stmt.where(LegalConversionOrder.status == "internal_processing")
    elif tab == "closed":
        stmt = stmt.where(
            LegalConversionOrder.status.in_(
                ("closed_paid", "closed_promised", "closed_uncollectible",
                 "escalated_to_lawfirm")
            )
        )
    # tab == 'all' 不过滤

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(desc(LegalConversionOrder.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 批量补充 last_action_at + action_count + requester_name
    order_ids = [o.id for o, _ in rows]
    action_stats: dict[int, tuple[datetime | None, int]] = {}
    if order_ids:
        for oid, last_at, cnt in db.execute(
            select(
                LegalInternalAction.legal_order_id,
                func.max(LegalInternalAction.occurred_at),
                func.count(LegalInternalAction.id),
            )
            .where(LegalInternalAction.legal_order_id.in_(order_ids))
            .group_by(LegalInternalAction.legal_order_id)
        ).all():
            action_stats[int(oid)] = (last_at, int(cnt))

    requester_map: dict[int, str] = {}
    if order_ids:
        for req_user, order_id in db.execute(
            select(UserAccount.name, LegalConversionRequest.related_order_id)
            .join(
                LegalConversionRequest,
                LegalConversionRequest.requester_user_id == UserAccount.id,
            )
            .where(LegalConversionRequest.related_order_id.in_(order_ids))
        ).all():
            requester_map[int(order_id)] = req_user

    items = [
        LegalInternalOrderListItem(
            id=o.id,
            case_id=o.case_id,
            owner_name=owner.name,
            owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal),
            building=owner.building,
            room=owner.room,
            amount_owed=db.get(CollectionCase, o.case_id).amount_owed,  # type: ignore[union-attr]
            months_overdue=db.get(CollectionCase, o.case_id).months_overdue,  # type: ignore[union-attr]
            status=o.status,
            created_at=o.created_at,
            requester_name=requester_map.get(o.id),
            last_action_at=action_stats.get(o.id, (None, 0))[0],
            action_count=action_stats.get(o.id, (None, 0))[1],
        )
        for o, owner in rows
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
    )


# ── Detail ────────────────────────────────────────────────────
@router.get("/internal-orders/{order_id}", response_model=LegalInternalOrderDetailOut)
def get_internal_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalOrderDetailOut:
    tenant_id = _require_tenant(payload)
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务订单不存在"},
        )
    case = db.get(CollectionCase, order.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case else None
    if not case or not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_GONE", "message": "案件或业主不存在"},
        )
    project_name = None
    if case.project_id:
        project_name = db.execute(
            select(Project.name).where(Project.id == case.project_id)
        ).scalar_one_or_none()

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    reveal = should_reveal_owner_phone(role=role, contract_active=contract_active)

    action_rows = db.execute(
        select(LegalInternalAction)
        .where(LegalInternalAction.legal_order_id == order_id)
        .order_by(LegalInternalAction.occurred_at.asc())
    ).scalars().all()
    actor_ids = {a.actor_user_id for a in action_rows}
    template_ids = {a.letter_template_id for a in action_rows if a.letter_template_id}
    firm_ids = {a.partner_law_firm_id for a in action_rows if a.partner_law_firm_id}
    actor_map = {
        uid: name for uid, name in db.execute(
            select(UserAccount.id, UserAccount.name).where(UserAccount.id.in_(actor_ids))
        ).all()
    } if actor_ids else {}
    template_map = {
        tid: name for tid, name in db.execute(
            select(InternalLegalLetterTemplate.id, InternalLegalLetterTemplate.name)
            .where(InternalLegalLetterTemplate.id.in_(template_ids))
        ).all()
    } if template_ids else {}
    firm_map = {
        fid: name for fid, name in db.execute(
            select(PartnerLawFirm.id, PartnerLawFirm.name)
            .where(PartnerLawFirm.id.in_(firm_ids))
        ).all()
    } if firm_ids else {}

    return LegalInternalOrderDetailOut(
        id=order.id,
        tenant_id=order.tenant_id,
        case_id=order.case_id,
        status=order.status,
        owner_name=owner.name,
        owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal),
        building=owner.building,
        room=owner.room,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        arrears_reason=case.arrears_reason,
        project_name=project_name,
        notes=order.notes,
        created_at=order.created_at,
        actions=[
            _action_to_out(
                a,
                actor_name=actor_map.get(a.actor_user_id),
                template_name=template_map.get(a.letter_template_id) if a.letter_template_id else None,
                law_firm_name=firm_map.get(a.partner_law_firm_id) if a.partner_law_firm_id else None,
            )
            for a in action_rows
        ],
        internal_close_reason=order.internal_close_reason,
        internal_closed_at=order.internal_closed_at,
    )


# ── Record action ─────────────────────────────────────────────
@router.post(
    "/internal-orders/{order_id}/actions",
    response_model=LegalInternalActionOut,
    status_code=http_status.HTTP_201_CREATED,
)
def record_internal_action(
    order_id: int,
    body: LegalInternalActionCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalActionOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务订单不存在"},
        )
    if order.status != "internal_processing":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_ORDER_CLOSED",
                "message": f"订单当前状态 {order.status}，不可再添加内部处理记录",
            },
        )
    # 校验 letter_template / partner_law_firm 归属
    if body.letter_template_id is not None:
        tpl = db.get(InternalLegalLetterTemplate, body.letter_template_id)
        if tpl is None or tpl.tenant_id != tenant_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_TEMPLATE_INVALID", "message": "律师函模板不存在"},
            )
    if body.partner_law_firm_id is not None:
        firm = db.get(PartnerLawFirm, body.partner_law_firm_id)
        if firm is None or firm.tenant_id != tenant_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_FIRM_INVALID", "message": "合作律所不存在"},
            )

    action = LegalInternalAction(
        tenant_id=tenant_id,
        legal_order_id=order_id,
        case_id=order.case_id,
        action_type=body.action_type,
        actor_user_id=user_id,
        occurred_at=datetime.now(UTC),
        note=body.note,
        letter_template_id=body.letter_template_id,
        partner_law_firm_id=body.partner_law_firm_id,
        attachment_key=body.attachment_key,
        attachment_filename=body.attachment_filename,
        letter_variables=body.letter_variables,
    )
    db.add(action)
    db.flush()

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_internal_action.recorded",
        target_type="legal_internal_action",
        target_id=action.id,
        payload={"order_id": order_id, "action_type": body.action_type},
    )
    db.commit()
    db.refresh(action)

    actor_name = db.execute(
        select(UserAccount.name).where(UserAccount.id == user_id)
    ).scalar_one_or_none()
    return _action_to_out(action, actor_name=actor_name)


# ── Close ─────────────────────────────────────────────────────
@router.post(
    "/internal-orders/{order_id}/close",
    response_model=LegalInternalOrderDetailOut,
)
def close_internal_order(
    order_id: int,
    body: LegalInternalOrderCloseRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalOrderDetailOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务订单不存在"},
        )
    if order.status != "internal_processing":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_ORDER_CLOSED",
                "message": f"订单当前状态 {order.status}，不可再次关闭",
            },
        )

    # 状态映射：close_reason → order.status
    new_status = {
        "paid": "closed_paid",
        "promised": "closed_promised",
        "uncollectible": "closed_uncollectible",
        "escalated": "escalated_to_lawfirm",
    }[body.close_reason]
    now = datetime.now(UTC)
    order.status = new_status
    order.internal_close_reason = body.close_reason
    order.internal_closed_at = now
    order.internal_closed_by = user_id
    if body.close_reason != "escalated":
        order.completed_at = now

    # 联动 case.stage
    case = db.get(CollectionCase, order.case_id)
    if case is not None:
        new_stage = _legal_stage_for_close_reason(body.close_reason)
        if new_stage is not None:
            case.stage = new_stage

    # 写一条 close 操作 action 留痕
    close_action = LegalInternalAction(
        tenant_id=tenant_id,
        legal_order_id=order_id,
        case_id=order.case_id,
        action_type="other",
        actor_user_id=user_id,
        occurred_at=now,
        note=body.note or f"订单关闭：{body.close_reason}",
    )
    db.add(close_action)
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_internal_order.closed",
        target_type="legal_conversion_order",
        target_id=order_id,
        payload={"close_reason": body.close_reason, "new_stage": new_stage if case else None},
    )
    db.commit()

    return get_internal_order(order_id, payload, _user, db)


# ── Escalate ──────────────────────────────────────────────────
@router.post(
    "/internal-orders/{order_id}/escalate",
    response_model=LegalInternalOrderDetailOut,
)
def escalate_to_lawfirm(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalOrderDetailOut:
    """v1.9.0 — 标记升级到律所。方案 C 才会真正派单到律所。"""
    return close_internal_order(
        order_id,
        LegalInternalOrderCloseRequest(close_reason="escalated", note="升级到律所，待律所撮合"),
        payload, _user, db,
    )
