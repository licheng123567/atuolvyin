"""v1.6 — 协商打折 / 减免审批 API。

POST   /api/v1/cases/{case_id}/discount-offers     创建（按 TenantSettings 自动判定）
GET    /api/v1/discount-offers                     列出（按角色过滤）
GET    /api/v1/discount-offers/{id}                详情
POST   /api/v1/discount-offers/{id}/approve        批准（角色须匹配 approver_role_required）
POST   /api/v1/discount-offers/{id}/reject         拒绝（reason 必填）
POST   /api/v1/discount-offers/{id}/escalate       supervisor → admin
POST   /api/v1/discount-offers/{id}/mark-executed  业主已按方案缴清（标记完成）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import (  # noqa: F401  Project 用于 _get_policy
    CollectionCase,
    OwnerProfile,
    Project,
)
from app.models.discount_offer import DiscountOffer
from app.models.settings import TenantSettings
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.discount import (
    DiscountActionRequest,
    DiscountOfferCreate,
    DiscountOfferOut,
    DiscountRejectRequest,
)
from app.services.audit import log_audit

router = APIRouter()

_OFFER_TYPE_LABELS = {
    "principal_discount": "本金减免",
    "late_fee_waive": "违约金减免",
    "installment": "分期还款",
    "long_overdue_compromise": "长账龄一次结清",
}

ALL_ROLES = (
    "agent",
    "supervisor",
    "admin",
    "superadmin",
)


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _get_policy(
    db: Session,
    tenant_id: int,
    project_id: int | None = None,
    offer_type: str = "principal_discount",
) -> tuple[int, int, bool]:
    """返回 (auto_threshold, supervisor_max, disabled)。

    优先级：Project（若该字段非 NULL）→ TenantSettings → 系统默认。
    v1.6.2 — 按 offer_type 路由：late_fee_waive 用「滞纳金减免」字段；其他用「本金打折」字段。
    """
    s = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()

    if offer_type == "late_fee_waive":
        auto = getattr(s, "late_fee_waive_auto_approve_threshold_pct", 50) if s else 50
        supervisor_max = getattr(s, "late_fee_waive_supervisor_max_pct", 100) if s else 100
        disabled = getattr(s, "late_fee_waive_disabled", False) if s else False
    else:
        # principal_discount / installment / long_overdue_compromise → 本金打折策略
        auto = s.discount_auto_approve_threshold_pct if s else 10
        supervisor_max = s.discount_supervisor_max_pct if s else 30
        disabled = s.discount_disabled if s else False

    if project_id is not None:
        p = db.get(Project, project_id)
        if p is not None:
            if offer_type == "late_fee_waive":
                if getattr(p, "late_fee_waive_auto_approve_threshold_pct", None) is not None:
                    auto = p.late_fee_waive_auto_approve_threshold_pct
                if getattr(p, "late_fee_waive_supervisor_max_pct", None) is not None:
                    supervisor_max = p.late_fee_waive_supervisor_max_pct
                if getattr(p, "late_fee_waive_disabled", None) is not None:
                    disabled = p.late_fee_waive_disabled
            else:
                if p.discount_auto_approve_threshold_pct is not None:
                    auto = p.discount_auto_approve_threshold_pct
                if p.discount_supervisor_max_pct is not None:
                    supervisor_max = p.discount_supervisor_max_pct
                if p.discount_disabled is not None:
                    disabled = p.discount_disabled
    return auto, supervisor_max, disabled


def _to_out(db: Session, offer: DiscountOffer) -> DiscountOfferOut:
    case = db.get(CollectionCase, offer.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
    project = db.get(Project, case.project_id) if case and case.project_id else None
    applicant = db.get(UserAccount, offer.applicant_user_id) if offer.applicant_user_id else None
    approver = db.get(UserAccount, offer.approved_by_user_id) if offer.approved_by_user_id else None
    out = DiscountOfferOut.model_validate(offer, from_attributes=True)
    out.applicant_name = applicant.name if applicant else None
    out.approved_by_name = approver.name if approver else None
    out.case_owner = owner.name if owner else None
    out.case_building = (owner.building or "") if owner else None
    out.project_name = project.name if project else None
    out.offer_type_label = _OFFER_TYPE_LABELS.get(offer.offer_type, offer.offer_type)
    return out


@router.get("/cases/{case_id}/discount-policy")
def get_effective_discount_policy(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.6.1 — 给定 case，返回当前生效的减免策略（项目级覆盖后）。

    前端发起减免前调用此接口，确保 UI 显示的阈值与后端实际判定一致。
    """
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )
    # v1.6.2 — 同时返回两类策略：本金打折 + 滞纳金减免
    pd_auto, pd_sup, pd_disabled = _get_policy(
        db, int(tenant_id), case.project_id, "principal_discount"
    )
    lf_auto, lf_sup, lf_disabled = _get_policy(
        db, int(tenant_id), case.project_id, "late_fee_waive"
    )
    project = db.get(Project, case.project_id) if case.project_id else None
    pd_overridden = bool(
        project
        and (
            project.discount_auto_approve_threshold_pct is not None
            or project.discount_supervisor_max_pct is not None
            or project.discount_disabled is not None
        )
    )
    lf_overridden = bool(
        project
        and (
            getattr(project, "late_fee_waive_auto_approve_threshold_pct", None) is not None
            or getattr(project, "late_fee_waive_supervisor_max_pct", None) is not None
            or getattr(project, "late_fee_waive_disabled", None) is not None
        )
    )
    return {
        "case_id": case_id,
        "project_id": case.project_id,
        "project_name": project.name if project else None,
        # 旧字段保留兼容（= 本金打折）
        "auto_threshold": pd_auto,
        "supervisor_max": pd_sup,
        "disabled": pd_disabled,
        "source": "project" if pd_overridden else "tenant",
        # v1.6.2 — 新增：明确区分两类策略
        "principal_discount": {
            "auto_threshold": pd_auto,
            "supervisor_max": pd_sup,
            "disabled": pd_disabled,
            "source": "project" if pd_overridden else "tenant",
        },
        "late_fee_waive": {
            "auto_threshold": lf_auto,
            "supervisor_max": lf_sup,
            "disabled": lf_disabled,
            "source": "project" if lf_overridden else "tenant",
        },
    }


@router.post("/cases/{case_id}/discount-offers", response_model=DiscountOfferOut)
def create_offer(
    case_id: int,
    body: DiscountOfferCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    user_id = int(payload["user_id"])
    role = payload.get("role", "")

    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )

    # v1.6.1/2 — 按 case.project_id + offer_type 解析策略（项目级覆盖租户级；类型区分本金/滞纳金）
    auto_threshold, supervisor_max, disabled = _get_policy(
        db, int(tenant_id), case.project_id, body.offer_type
    )
    if disabled:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_DISCOUNT_DISABLED",
                "message": "本项目已停用减免功能（admin 可在项目设置开启）",
            },
        )

    if body.proposed_amount > body.original_amount:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "业主同意支付金额不能超过原欠费"},
        )

    # 分期默认不打折
    proposed = body.original_amount if body.offer_type == "installment" else body.proposed_amount

    discount_pct = 0
    if body.original_amount > 0:
        discount_pct = int(
            ((body.original_amount - proposed) / body.original_amount * Decimal(100)).quantize(
                Decimal("1")
            )
        )
    discount_pct = max(0, min(100, discount_pct))

    # 决策路由
    if discount_pct < auto_threshold:
        status = "approved"
        approver_role_required = "supervisor"
        approved_by_user_id: int | None = None  # 系统自动
        approved_at: datetime | None = datetime.now(UTC)
    elif discount_pct <= supervisor_max:
        status = "pending_supervisor"
        approver_role_required = "supervisor"
        approved_by_user_id = None
        approved_at = None
    else:
        status = "pending_admin"
        approver_role_required = "admin"
        approved_by_user_id = None
        approved_at = None

    applicant_role = "supervisor" if role == "supervisor" else "agent"
    user = db.get(UserAccount, user_id)
    applicant_name = user.name if user else "未知"

    audit: list[dict] = [
        {
            "time": _now_str(),
            "actor": applicant_name,
            "action": f"发起{_OFFER_TYPE_LABELS[body.offer_type]}申请（{discount_pct}%）",
        }
    ]
    if status == "approved":
        audit.append(
            {
                "time": _now_str(),
                "actor": "系统",
                "action": f"自动批准（折扣 < {auto_threshold}%）",
            }
        )

    offer = DiscountOffer(
        tenant_id=int(tenant_id),
        case_id=case_id,
        provider_id=payload.get("provider_id"),
        applicant_user_id=user_id,
        applicant_role=applicant_role,
        offer_type=body.offer_type,
        original_amount=body.original_amount,
        proposed_amount=proposed,
        discount_pct=discount_pct,
        installment_months=body.installment_months,
        reason=body.reason,
        status=status,
        approver_role_required=approver_role_required,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        audit_trail=audit,
    )
    db.add(offer)
    db.flush()

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=int(tenant_id),
        action="discount_offer.create",
        target_type="discount_offer",
        target_id=offer.id,
        payload={"discount_pct": discount_pct, "status": status},
    )
    db.commit()
    db.refresh(offer)
    return _to_out(db, offer)


@router.get("/discount-offers", response_model=PaginatedResponse[DiscountOfferOut])
def list_offers(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    my_pending: Annotated[bool, Query()] = False,
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[DiscountOfferOut]:
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    stmt = (
        select(DiscountOffer)
        .where(DiscountOffer.tenant_id == int(tenant_id))
        .order_by(desc(DiscountOffer.id))
    )
    if status:
        stmt = stmt.where(DiscountOffer.status == status)
    if my_pending:
        if role == "supervisor":
            stmt = stmt.where(DiscountOffer.status == "pending_supervisor")
        elif role == "admin":
            stmt = stmt.where(DiscountOffer.status == "pending_admin")

    total = len(db.execute(stmt.with_only_columns(DiscountOffer.id)).all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        items=[_to_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/discount-offers/{offer_id}", response_model=DiscountOfferOut)
def get_offer(
    offer_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    offer = db.get(DiscountOffer, offer_id)
    if not offer or offer.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "申请不存在或不属于本租户"},
        )
    return _to_out(db, offer)


def _load_offer_or_404(db: Session, offer_id: int, tenant_id: int) -> DiscountOffer:
    offer = db.get(DiscountOffer, offer_id)
    if not offer or offer.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "申请不存在或不属于本租户"},
        )
    return offer


def _append_audit(offer: DiscountOffer, actor: str, action: str) -> None:
    trail = list(offer.audit_trail or [])
    trail.append({"time": _now_str(), "actor": actor, "action": action})
    offer.audit_trail = trail
    flag_modified(offer, "audit_trail")


@router.post("/discount-offers/{offer_id}/approve", response_model=DiscountOfferOut)
def approve_offer(
    offer_id: int,
    body: DiscountActionRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "")
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "未知"

    offer = _load_offer_or_404(db, offer_id, int(tenant_id))
    if offer.status not in {"pending_supervisor", "pending_admin"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_INVALID_STATE", "message": f"当前状态 {offer.status} 不可批准"},
        )
    if offer.status == "pending_supervisor" and role != "supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_SUPERVISOR", "message": "需督导角色批准"},
        )
    if offer.status == "pending_admin" and role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_ADMIN", "message": "需 admin 角色批准"},
        )
    offer.status = "approved"
    offer.approved_by_user_id = user_id
    offer.approved_at = datetime.now(UTC)
    note = body.note or ""
    _append_audit(offer, actor_name, f"批准{('（' + note + '）') if note else ''}")
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=int(tenant_id),
        action="discount_offer.approve",
        target_type="discount_offer",
        target_id=offer.id,
        payload={"note": note},
    )
    db.commit()
    db.refresh(offer)
    return _to_out(db, offer)


@router.post("/discount-offers/{offer_id}/reject", response_model=DiscountOfferOut)
def reject_offer(
    offer_id: int,
    body: DiscountRejectRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "")
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "未知"

    offer = _load_offer_or_404(db, offer_id, int(tenant_id))
    if offer.status not in {"pending_supervisor", "pending_admin"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_INVALID_STATE", "message": f"当前状态 {offer.status} 不可拒绝"},
        )
    if offer.status == "pending_supervisor" and role != "supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN, detail={"code": "ERR_NOT_SUPERVISOR"}
        )
    if offer.status == "pending_admin" and role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN, detail={"code": "ERR_NOT_ADMIN"}
        )

    offer.status = "rejected"
    offer.rejected_reason = body.reason
    offer.approved_at = datetime.now(UTC)
    _append_audit(offer, actor_name, f"拒绝 — {body.reason}")
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=int(tenant_id),
        action="discount_offer.reject",
        target_type="discount_offer",
        target_id=offer.id,
        payload={"reason": body.reason},
    )
    db.commit()
    db.refresh(offer)
    return _to_out(db, offer)


@router.post("/discount-offers/{offer_id}/escalate", response_model=DiscountOfferOut)
def escalate_offer(
    offer_id: int,
    body: DiscountActionRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "")
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "未知"

    offer = _load_offer_or_404(db, offer_id, int(tenant_id))
    if role != "supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_SUPERVISOR", "message": "仅督导可转交 admin"},
        )
    if offer.status != "pending_supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_INVALID_STATE", "message": f"当前状态 {offer.status} 不可转交"},
        )
    offer.status = "pending_admin"
    offer.approver_role_required = "admin"
    note = body.note or ""
    _append_audit(offer, actor_name, f"转交 admin 审批{('（' + note + '）') if note else ''}")
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=int(tenant_id),
        action="discount_offer.escalate",
        target_type="discount_offer",
        target_id=offer.id,
        payload={"note": note},
    )
    db.commit()
    db.refresh(offer)
    return _to_out(db, offer)


@router.post("/discount-offers/{offer_id}/mark-executed", response_model=DiscountOfferOut)
def mark_executed(
    offer_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DiscountOfferOut:
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "")
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "未知"

    offer = _load_offer_or_404(db, offer_id, int(tenant_id))
    if offer.status != "approved":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATE",
                "message": f"仅 approved 状态可标记已执行（当前 {offer.status}）",
            },
        )
    offer.status = "executed"
    _append_audit(offer, actor_name, "业主已按方案缴清 — offer 完成")
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=int(tenant_id),
        action="discount_offer.execute",
        target_type="discount_offer",
        target_id=offer.id,
        payload={},
    )
    db.commit()
    db.refresh(offer)
    return _to_out(db, offer)
