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

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_roles
from app.core.storage import storage
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
    LegalInternalOrderKpi,
    LegalInternalOrderListItem,
    LegalInternalOrderReopenRequest,
)
from app.services.audit import log_audit
from app.services.evidence_bundle import build_evidence_bundle_zip

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


# ── KPI ───────────────────────────────────────────────────────
# v1.9.2 — 法务工作台顶部 4 张 KPI 卡
@router.get("/internal-orders/kpi", response_model=LegalInternalOrderKpi)
def get_internal_orders_kpi(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalOrderKpi:
    tenant_id = _require_tenant(payload)
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    pending_count = (
        db.execute(
            select(func.count(LegalConversionOrder.id))
            .where(LegalConversionOrder.tenant_id == tenant_id)
            .where(LegalConversionOrder.status == "internal_processing")
        ).scalar_one()
        or 0
    )

    closed_statuses = ("closed_paid", "closed_promised", "closed_uncollectible")
    closed_this_month = (
        db.execute(
            select(func.count(LegalConversionOrder.id))
            .where(LegalConversionOrder.tenant_id == tenant_id)
            .where(LegalConversionOrder.status.in_(closed_statuses))
            .where(LegalConversionOrder.internal_closed_at.is_not(None))
            .where(LegalConversionOrder.internal_closed_at >= month_start)
        ).scalar_one()
        or 0
    )

    escalated_this_month = (
        db.execute(
            select(func.count(LegalConversionOrder.id))
            .where(LegalConversionOrder.tenant_id == tenant_id)
            .where(LegalConversionOrder.status == "escalated_to_lawfirm")
            .where(LegalConversionOrder.internal_closed_at.is_not(None))
            .where(LegalConversionOrder.internal_closed_at >= month_start)
        ).scalar_one()
        or 0
    )

    # 平均处理时长（天）：本月所有已关闭/升级的订单 (closed_at - created_at) 平均
    avg_seconds = db.execute(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    LegalConversionOrder.internal_closed_at - LegalConversionOrder.created_at,
                )
            )
        )
        .where(LegalConversionOrder.tenant_id == tenant_id)
        .where(LegalConversionOrder.internal_closed_at.is_not(None))
        .where(LegalConversionOrder.internal_closed_at >= month_start)
    ).scalar()
    avg_days = round(float(avg_seconds) / 86400.0, 1) if avg_seconds is not None else None

    total_finalized = closed_this_month + escalated_this_month
    escalation_rate = (
        round(escalated_this_month / total_finalized * 100, 1) if total_finalized > 0 else None
    )

    return LegalInternalOrderKpi(
        pending_count=int(pending_count),
        closed_this_month=int(closed_this_month),
        avg_processing_days=avg_days,
        escalation_rate_pct=escalation_rate,
    )


# ── List ──────────────────────────────────────────────────────
@router.get(
    "/internal-orders",
    response_model=PaginatedResponse[LegalInternalOrderListItem],
)
def list_internal_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    tab: str = Query("pending", pattern="^(pending|closed|escalated|all)$"),
    project_id: int | None = Query(None, description="按所属项目过滤"),
    q: str | None = Query(None, max_length=100, description="搜索业主姓名/房号"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalInternalOrderListItem]:
    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    # v1.9.0 — legal 角色处理内部订单时（无论是 internal_processing 进行中还是已关闭/升级）
    # 都需要明文电话用于发律师函/电话沟通；其他角色按 v1.7.0 决策
    reveal = (
        True
        if role == "legal"
        else should_reveal_owner_phone(role=role, provider_id=payload.get("provider_id"), contract_active=contract_active)
    )

    stmt = (
        select(LegalConversionOrder, OwnerProfile, CollectionCase, Project)
        .join(CollectionCase, CollectionCase.id == LegalConversionOrder.case_id)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(LegalConversionOrder.tenant_id == tenant_id)
    )
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if q:
        from sqlalchemy import or_ as sa_or_

        stmt = stmt.where(
            sa_or_(
                OwnerProfile.name.ilike(f"%{q}%"),
                OwnerProfile.room.ilike(f"%{q}%"),
            )
        )
    if tab == "pending":
        stmt = stmt.where(LegalConversionOrder.status == "internal_processing")
    elif tab == "closed":
        stmt = stmt.where(
            LegalConversionOrder.status.in_(
                ("closed_paid", "closed_promised", "closed_uncollectible")
            )
        )
    elif tab == "escalated":
        # v1.9.1 — 升级律所追踪页：单独过滤 escalated_to_lawfirm 订单（方案 C 派单前法务可加跟进备注）
        stmt = stmt.where(LegalConversionOrder.status == "escalated_to_lawfirm")
    # tab == 'all' 不过滤

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(desc(LegalConversionOrder.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 批量补充 last_action_at + action_count + requester_name
    order_ids = [o.id for o, _owner, _case, _proj in rows]
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
            amount_owed=case.amount_owed if case else None,
            months_overdue=case.months_overdue if case else None,
            status=o.status,
            created_at=o.created_at,
            requester_name=requester_map.get(o.id),
            last_action_at=action_stats.get(o.id, (None, 0))[0],
            action_count=action_stats.get(o.id, (None, 0))[1],
            promise_due_date=o.promise_due_date,
            project_id=case.project_id if case else None,
            project_name=proj.name if proj else None,
        )
        for o, owner, case, proj in rows
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
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
    # v1.9.0 — legal 角色处理内部订单时（无论是 internal_processing 进行中还是已关闭/升级）
    # 都需要明文电话用于发律师函/电话沟通；其他角色按 v1.7.0 决策
    reveal = (
        True
        if role == "legal"
        else should_reveal_owner_phone(role=role, provider_id=payload.get("provider_id"), contract_active=contract_active)
    )

    action_rows = (
        db.execute(
            select(LegalInternalAction)
            .where(LegalInternalAction.legal_order_id == order_id)
            .order_by(LegalInternalAction.occurred_at.asc())
        )
        .scalars()
        .all()
    )
    actor_ids = {a.actor_user_id for a in action_rows}
    template_ids = {a.letter_template_id for a in action_rows if a.letter_template_id}
    firm_ids = {a.partner_law_firm_id for a in action_rows if a.partner_law_firm_id}
    actor_map = (
        {
            uid: name
            for uid, name in db.execute(
                select(UserAccount.id, UserAccount.name).where(UserAccount.id.in_(actor_ids))
            ).all()
        }
        if actor_ids
        else {}
    )
    template_map = (
        {
            tid: name
            for tid, name in db.execute(
                select(InternalLegalLetterTemplate.id, InternalLegalLetterTemplate.name).where(
                    InternalLegalLetterTemplate.id.in_(template_ids)
                )
            ).all()
        }
        if template_ids
        else {}
    )
    firm_map = (
        {
            fid: name
            for fid, name in db.execute(
                select(PartnerLawFirm.id, PartnerLawFirm.name).where(
                    PartnerLawFirm.id.in_(firm_ids)
                )
            ).all()
        }
        if firm_ids
        else {}
    )

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
                template_name=template_map.get(a.letter_template_id)
                if a.letter_template_id
                else None,
                law_firm_name=firm_map.get(a.partner_law_firm_id)
                if a.partner_law_firm_id
                else None,
            )
            for a in action_rows
        ],
        internal_close_reason=order.internal_close_reason,
        internal_closed_at=order.internal_closed_at,
        promise_due_date=order.promise_due_date,
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
    # v1.9.1 — promised 必须填承诺到期日
    if body.close_reason == "promised" and body.promise_due_date is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_PROMISE_DATE_REQUIRED", "message": "已承诺关闭必须填写承诺到期日"},
        )
    now = datetime.now(UTC)
    order.status = new_status
    order.internal_close_reason = body.close_reason
    order.internal_closed_at = now
    order.internal_closed_by = user_id
    order.promise_due_date = body.promise_due_date if body.close_reason == "promised" else None
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
        payload,
        _user,
        db,
    )


# ── Reopen ────────────────────────────────────────────────────
@router.post(
    "/internal-orders/{order_id}/reopen",
    response_model=LegalInternalOrderDetailOut,
)
def reopen_internal_order(
    order_id: int,
    body: LegalInternalOrderReopenRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalInternalOrderDetailOut:
    """v1.9.1 — closed_promised 但承诺到期未付，重新打开订单回 internal_processing。

    仅允许 closed_promised → internal_processing；其他状态返回 409。
    """
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务订单不存在"},
        )
    if order.status != "closed_promised":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_NOT_REOPENABLE",
                "message": f"仅 closed_promised 状态可重新打开（当前 {order.status}）",
            },
        )

    order.status = "internal_processing"
    order.internal_close_reason = None
    order.internal_closed_at = None
    order.internal_closed_by = None
    order.completed_at = None

    # 联动 case.stage 回 legal（v1.9.1：close_promised 时是 promised → 重开回 legal）
    case = db.get(CollectionCase, order.case_id)
    if case is not None:
        case.stage = "legal"

    # 写一条 reopen action 留痕
    reopen_action = LegalInternalAction(
        tenant_id=tenant_id,
        legal_order_id=order_id,
        case_id=order.case_id,
        action_type="other",
        actor_user_id=user_id,
        occurred_at=datetime.now(UTC),
        note=body.note or f"承诺到期未付，重新打开订单（原承诺到期：{order.promise_due_date}）",
    )
    db.add(reopen_action)
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_internal_order.reopened",
        target_type="legal_conversion_order",
        target_id=order_id,
        payload={
            "original_promise_due_date": str(order.promise_due_date)
            if order.promise_due_date
            else None
        },
    )
    # promise_due_date 保留作为审计；如果再次 close_promised 时会被新值覆盖
    db.commit()

    return get_internal_order(order_id, payload, _user, db)


# ── Attachment upload / download ──────────────────────────────
# v1.9.1 — 律师函 / 催告函盖章版 PDF 上传，绑定到对应 send_lawyer_letter / send_notice action

# 单文件最大 10 MB（律师函 PDF 通常几百 KB 到 1-2 MB）
ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
ATTACHMENT_ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg"}
ATTACHMENT_ELIGIBLE_ACTIONS = {"send_lawyer_letter", "send_notice"}


@router.post(
    "/internal-orders/{order_id}/actions/{action_id}/attachment",
    response_model=LegalInternalActionOut,
)
def upload_action_attachment(
    order_id: int,
    action_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> LegalInternalActionOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")

    action = db.get(LegalInternalAction, action_id)
    if action is None or action.tenant_id != tenant_id or action.legal_order_id != order_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_ACTION_NOT_FOUND", "message": "处理记录不存在"},
        )
    if action.action_type not in ATTACHMENT_ELIGIBLE_ACTIONS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_ACTION_TYPE",
                "message": "仅律师函 / 催告函记录可上传盖章版附件",
            },
        )
    content_type = (file.content_type or "").lower()
    if content_type not in ATTACHMENT_ALLOWED_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_FILE_TYPE",
                "message": "仅支持 PDF / PNG / JPG 格式",
            },
        )
    data = file.file.read(ATTACHMENT_MAX_BYTES + 1)
    if len(data) > ATTACHMENT_MAX_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "ERR_FILE_TOO_LARGE", "message": "文件超过 10 MB 上限"},
        )

    safe_name = (file.filename or "letter").replace("/", "_").replace("\\", "_")[:200]
    object_key = f"legal-letters/{tenant_id}/{order_id}/{action_id}/{safe_name}"
    storage.put_object(object_key, data, content_type)

    action.attachment_key = object_key
    action.attachment_filename = safe_name
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_internal_action.attachment_uploaded",
        target_type="legal_internal_action",
        target_id=action_id,
        payload={"order_id": order_id, "filename": safe_name, "size": len(data)},
    )
    db.commit()
    db.refresh(action)

    actor_name = db.execute(
        select(UserAccount.name).where(UserAccount.id == action.actor_user_id)
    ).scalar_one_or_none()
    template_name = None
    if action.letter_template_id:
        template_name = db.execute(
            select(InternalLegalLetterTemplate.name).where(
                InternalLegalLetterTemplate.id == action.letter_template_id
            )
        ).scalar_one_or_none()
    firm_name = None
    if action.partner_law_firm_id:
        firm_name = db.execute(
            select(PartnerLawFirm.name).where(PartnerLawFirm.id == action.partner_law_firm_id)
        ).scalar_one_or_none()
    return _action_to_out(
        action,
        actor_name=actor_name,
        template_name=template_name,
        law_firm_name=firm_name,
    )


@router.get(
    "/internal-orders/{order_id}/actions/{action_id}/attachment",
)
def download_action_attachment(
    order_id: int,
    action_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    tenant_id = _require_tenant(payload)
    action = db.get(LegalInternalAction, action_id)
    if action is None or action.tenant_id != tenant_id or action.legal_order_id != order_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_ACTION_NOT_FOUND", "message": "处理记录不存在"},
        )
    if not action.attachment_key:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_ATTACHMENT", "message": "该记录未上传附件"},
        )
    try:
        data = storage.get_bytes(action.attachment_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_FILE_GONE", "message": f"附件文件不可读：{exc!s}"},
        ) from exc
    filename = action.attachment_filename or "attachment"
    # Content-Type 推断：根据文件名后缀
    ct = "application/pdf"
    if filename.lower().endswith((".png",)):
        ct = "image/png"
    elif filename.lower().endswith((".jpg", ".jpeg")):
        ct = "image/jpeg"
    return Response(
        content=data,
        media_type=ct,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ── Evidence bundle (v1.9.5) ──────────────────────────────
@router.get("/internal-orders/{order_id}/evidence-bundle")
def download_internal_order_evidence_bundle(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """v1.9.5 — 按法务订单的关联案件打包证据（录音/转写/AI/区块链 + 法务处理流水 + 律师函附件）。"""
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")

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
            detail={"code": "ERR_CASE_GONE", "message": "案件或业主信息缺失"},
        )

    # 法务处理订单上下文 → 永远展示明文电话（与详情页一致）
    reveal = role == "legal" or should_reveal_owner_phone(
        role=role,
        provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
    )

    buffer, filename = build_evidence_bundle_zip(
        db,
        tenant_id=tenant_id,
        case=case,
        owner=owner,
        owner_phone_display=display_owner_phone(owner.phone_enc, reveal=reveal),
        case_summary_extra={
            "internal_order_id": order.id,
            "internal_order_status": order.status,
            "internal_close_reason": order.internal_close_reason,
            "internal_closed_at": order.internal_closed_at.isoformat()
            if order.internal_closed_at
            else None,
            "promise_due_date": order.promise_due_date.isoformat()
            if order.promise_due_date
            else None,
        },
        user_id=user_id or None,
        legal_order_id=order.id,
    )

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_internal_order.evidence_bundle_downloaded",
        target_type="legal_conversion_order",
        target_id=order_id,
        payload={"case_id": order.case_id, "filename": filename},
    )
    db.commit()

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
