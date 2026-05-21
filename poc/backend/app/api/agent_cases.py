from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import LegalConversionOrder, LegalConversionRequest
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.case import (
    CaseDetailResponse,
    CaseResponse,
    CaseStageUpdate,
    CaseWithOwnerResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.audit import log_audit

from .admin_cases import _case_row_to_response, _require_tenant, build_case_detail_response


def _agent_membership(db: Session, user_id: int, tenant_id: int) -> UserTenantMembership | None:
    """Return the agent's membership row for this tenant."""
    return (
        db.execute(
            sa.select(UserTenantMembership).where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "agent",
            )
        )
        .scalars()
        .first()
    )


def _build_visible_case_filter(db: Session, user_id: int, tenant_id: int, role: str):
    """Build SQLAlchemy WHERE clause for cases visible to the agent.

    内勤（work_mode=internal）：私海（自己的）+ 公海（无项目 OR 项目无服务商 OR 项目允许协助）
    外勤（work_mode=external）：私海（自己的）+ 公海（项目 provider_id == 我的 provider_id）
    """
    own_clause = CollectionCase.assigned_to == user_id

    m = _agent_membership(db, user_id, tenant_id)
    work_mode = m.work_mode if m else None
    provider_id = m.provider_id if m else None

    if work_mode == "external":
        if provider_id is None:
            return own_clause
        # 外勤可见：自己的 OR 公海 + 本服务商负责的「服务期内 active」项目
        # v1.5.5 — 加 status='active' + plan_end 守门
        external_visible = sa.and_(
            CollectionCase.pool_type == "public",
            CollectionCase.assigned_to.is_(None),
            CollectionCase.project_id.in_(
                sa.select(Project.id).where(
                    Project.tenant_id == tenant_id,
                    Project.provider_id == provider_id,
                    Project.status == "active",
                    sa.or_(Project.plan_end.is_(None), Project.plan_end >= sa.func.now()),
                )
            ),
        )
        return sa.or_(own_clause, external_visible)

    # 内勤：自己的 + 公海（仅自办项目；外包项目完全归服务商，不再支持混合协助）
    # v1.5.6 收尾 — 砍 allow_internal_assist；项目要么自办要么外包，二选一
    visible_project_ids = sa.select(Project.id).where(
        Project.tenant_id == tenant_id,
        Project.status == "active",
        sa.or_(Project.plan_end.is_(None), Project.plan_end >= sa.func.now()),
        Project.provider_id.is_(None),  # 仅自办
    )
    internal_visible = sa.and_(
        CollectionCase.pool_type == "public",
        CollectionCase.assigned_to.is_(None),
        sa.or_(
            CollectionCase.project_id.is_(None),
            CollectionCase.project_id.in_(visible_project_ids),
        ),
    )
    return sa.or_(own_clause, internal_visible)


router = APIRouter()

AGENT_ROLES = ("agent",)


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_my_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    pool_type: str | None = Query(None),
    stage: str | None = Query(None),
    project_id: int | None = Query(None),
    q: str | None = Query(None, description="搜索业主姓名 / 房号"),
    today: bool = Query(
        False, description="只展示今日待联系：未结案 + (今天没联系过 OR 上次联系超过 7 天)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")

    # v1.4 — 按 agent 角色 + 项目 provider_id + allow_internal_assist 过滤
    visible_clause = _build_visible_case_filter(db, user.id, tenant_id, role)
    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            visible_clause,
        )
    )
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if q and q.strip():
        kw = f"%{q.strip()}%"
        stmt = stmt.where(
            sa.or_(
                OwnerProfile.name.ilike(kw),
                OwnerProfile.building.ilike(kw),
                OwnerProfile.room.ilike(kw),
            )
        )
    if today:
        # v1.6.7 — 今日聚合：未缴清未关闭，且今天还没拨过 / 拨了 > 7 天没回访
        from datetime import UTC, timedelta
        from datetime import datetime as _dt

        now = _dt.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        stmt = stmt.where(
            CollectionCase.stage.notin_(("paid", "closed")),
            sa.or_(
                CollectionCase.last_contact_at.is_(None),
                CollectionCase.last_contact_at < today_start,
                CollectionCase.last_contact_at < week_ago,
            ),
            OwnerProfile.do_not_call.is_(False),
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(
            CollectionCase.assigned_to.desc().nulls_last(),
            CollectionCase.priority_score.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 批量解析 project_name（避免 N+1）
    project_ids = {case.project_id for case, _ in rows if case.project_id}
    project_name_map: dict[int, str] = {}
    if project_ids:
        for pid, pname in db.execute(
            sa.select(Project.id, Project.name).where(Project.id.in_(project_ids))
        ).all():
            project_name_map[pid] = pname

    # v1.7.0 — agent(internal) 永远明文；agent(external) 看合同有效性（项目级 plan_end 暂不入列表，
    # 单条详情页再细查；列表层只看合同总开关）
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    owner_phone_reveal = should_reveal_owner_phone(
        role=role, provider_id=payload.get("provider_id"), contract_active=contract_active
    )

    return PaginatedResponse(
        items=[
            _case_row_to_response(
                case,
                owner,
                project_name=project_name_map.get(case.project_id) if case.project_id else None,
                owner_phone_reveal=owner_phone_reveal,
            )
            for case, owner in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


class AgentProjectOption(BaseModel):
    id: int
    name: str


@router.get("/me/projects", response_model=list[AgentProjectOption])
async def list_my_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[AgentProjectOption]:
    """催收员可见的项目下拉选项（distinct project_id 来自 visible cases）。"""
    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")
    visible_clause = _build_visible_case_filter(db, user.id, tenant_id, role)
    rows = db.execute(
        sa.select(Project.id, Project.name)
        .join(CollectionCase, CollectionCase.project_id == Project.id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            visible_clause,
            Project.id.isnot(None),
        )
        .distinct()
        .order_by(Project.name)
    ).all()
    return [AgentProjectOption(id=r[0], name=r[1]) for r in rows]


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
    role: str = payload.get("role", "")

    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner = row[0], row[1]

    # v1.4 — 复用 list 同样的可见性规则（含项目+服务商+协助开关）
    visible_clause = _build_visible_case_filter(db, user.id, tenant_id, role)
    visible_case = db.execute(
        select(CollectionCase.id).where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
            visible_clause,
        )
    ).scalar_one_or_none()
    if visible_case is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权访问此案件"},
        )

    # v1.6.6 — 复用 admin 同款 helper；work_mode=internal 拿到明文手机号用于拨号
    # v1.7.0 — 传 viewer 角色让 phone_masked 字段动态决定明文 / 脱敏
    mem = _agent_membership(db, user.id, tenant_id)
    is_internal = mem.work_mode == "internal" if mem else False
    return build_case_detail_response(
        db,
        case,
        owner,
        tenant_id=tenant_id,
        include_phone_plain=is_internal,
        viewer_role=role,
        viewer_provider_id=payload.get("provider_id"),
    )


@router.patch("/cases/{case_id}/stage", response_model=CaseResponse)
async def agent_update_case_stage(
    case_id: int,
    body: CaseStageUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    """v1.6.6 — 催收员更新自己的案件阶段（带跟进备注，写入 audit log）。

    权限：仅可更新 assigned_to == 自己 的案件。
    """
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.assigned_to != user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "只能更新分配给自己的案件"},
        )
    prev_stage = case.stage
    case.stage = body.stage
    db.commit()
    db.refresh(case)
    log_audit(
        db,
        actor_user_id=user.id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.stage_changed",
        target_type="collection_case",
        target_id=case_id,
        payload={"from": prev_stage, "to": body.stage, "note": body.note}
        if body.note
        else {"from": prev_stage, "to": body.stage},
    )
    db.commit()
    return case


_CASE_INTENT_ACTIONS = {"transfer_supervisor", "transfer_legal"}


class _CaseIntentIn(BaseModel):
    action: str
    note: str | None = None


class _CaseIntentOut(BaseModel):
    case_id: int
    action: str
    recorded_at: datetime
    status: str  # "queued"


@router.post("/cases/{case_id}/intent", response_model=_CaseIntentOut, status_code=201)
def post_case_intent(
    case_id: int,
    body: _CaseIntentIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> _CaseIntentOut:
    """Sprint 16 — 坐席案件级意向 stub（转主管/转法务）。

    真实派发流程（v1.x 主管 inbox / 法务转化撮合）尚未上线；本端点产出 audit_log 痕迹。
    """
    if body.action not in _CASE_INTENT_ACTIONS:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_INTENT", "message": "未知的意向动作"},
        )
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = str(payload.get("role") or "")

    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )

    # v1.6.8 — transfer_legal 走两步审批：催收员申请 → 督导/admin 批准 → 真正建单
    if body.action == "transfer_legal":
        # 已存在 active 法务订单 → 不允许再申请
        active_order = db.execute(
            select(LegalConversionOrder).where(
                LegalConversionOrder.case_id == case_id,
                LegalConversionOrder.status.in_(("pending", "dispatched", "in_service")),
            )
        ).scalar_one_or_none()
        if active_order is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "code": "ERR_LEGAL_ORDER_EXISTS",
                    "message": "该案件已存在进行中的法务转化订单",
                },
            )
        # 同案件已有 pending 申请 → 不允许重复申请
        pending_req = db.execute(
            select(LegalConversionRequest).where(
                LegalConversionRequest.case_id == case_id,
                LegalConversionRequest.status == "pending",
            )
        ).scalar_one_or_none()
        if pending_req is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "code": "ERR_REQUEST_PENDING",
                    "message": "该案件已有待审批的转法务申请",
                },
            )
        request_row = LegalConversionRequest(
            tenant_id=tenant_id,
            case_id=case_id,
            requester_user_id=user_id,
            requester_role=role,
            reason=body.note,
            status="pending",
        )
        db.add(request_row)
        db.flush()
        log_audit(
            db,
            actor_user_id=user_id,
            actor_role=role,
            tenant_id=tenant_id,
            action="legal_conversion_request.created",
            target_type="legal_conversion_request",
            target_id=request_row.id,
            payload={"case_id": case_id, "reason": body.note}
            if body.note
            else {"case_id": case_id},
        )

    now = datetime.now(UTC)
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action=f"case.intent.{body.action}",
        target_type="collection_case",
        target_id=case_id,
        payload={"note": body.note} if body.note else None,
    )
    db.commit()
    return _CaseIntentOut(case_id=case_id, action=body.action, recorded_at=now, status="queued")


class _PaymentLinkOut(BaseModel):
    case_id: int
    link: str
    short_link: str
    sent_to: str  # masked phone
    sent_at: datetime
    expires_at: datetime
    sms_status: str  # "queued" / "sent" / "skipped"


@router.post("/cases/{case_id}/send-payment-link", response_model=_PaymentLinkOut, status_code=201)
def send_payment_link(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> _PaymentLinkOut:
    """v1.6.7 — E4 一键发送缴费链接给业主（PoC：生成短链 + 写 audit log，不真实下发短信）。

    业务流程：
    - 校验 case 属于当前 agent + tenant
    - 生成短链 token + H5 缴费链接
    - 写 audit log（actor / case_id / sent_to_phone_masked）
    - 短信通道接入留 TODO（sms_status='queued'）
    """
    from datetime import timedelta
    from secrets import token_urlsafe

    from app.core.crypto import mask_phone

    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    # 仅可发送 assigned_to == 自己 的案件
    if case.assigned_to != user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "只能给分配给自己的案件发送链接"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    if not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_OWNER_MISSING", "message": "案件未关联业主"},
        )

    token = token_urlsafe(12)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=7)
    full_link = f"https://pay.autoluyin.example.com/h5/{token}"
    short_link = f"https://yzhc.cn/p/{token[:6]}"
    sent_to_masked = mask_phone(owner.phone_enc)

    log_audit(
        db,
        actor_user_id=user.id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.payment_link_sent",
        target_type="collection_case",
        target_id=case_id,
        payload={
            "owner_phone_masked": sent_to_masked,
            "amount": str(case.amount_owed) if case.amount_owed else None,
            "short_link": short_link,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()

    return _PaymentLinkOut(
        case_id=case_id,
        link=full_link,
        short_link=short_link,
        sent_to=sent_to_masked,
        sent_at=now,
        expires_at=expires_at,
        sms_status="queued",  # 真实短信通道接入后改为 'sent'
    )


_OPEN_STAGES = (
    "new",
    "in_progress",
    "promised",
    "escalated",
)  # 未结案的 stages（不含 paid/closed）


def _claim_quota(db: Session, *, tenant_id: int) -> int:
    """Return tenant's `public_pool_claim_max` (default 50 if no settings row)."""
    from app.models.settings import TenantSettings

    row = db.execute(
        select(TenantSettings.public_pool_claim_max).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return int(row) if row is not None else 50


def _agent_open_case_count(db: Session, *, user_id: int, tenant_id: int) -> int:
    return int(
        db.execute(
            select(func.count(CollectionCase.id)).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.assigned_to == user_id,
                CollectionCase.stage.in_(_OPEN_STAGES),
            )
        ).scalar_one()
    )


@router.get("/me/pool-quota")
async def get_pool_quota(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """v1.6.9 — 当前持有未结案案件数 + 抢单上限（让前端公海页展示进度）。"""
    tenant_id = _require_tenant(payload)
    held = _agent_open_case_count(db, user_id=user.id, tenant_id=tenant_id)
    quota = _claim_quota(db, tenant_id=tenant_id)
    return {
        "held_open": held,
        "claim_max": quota,
        "can_claim_more": held < quota,
        "remaining": max(0, quota - held),
    }


@router.post("/cases/{case_id}/claim", response_model=CaseResponse)
async def claim_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    role = str(payload.get("role") or "")

    # v1.6.9 — 持有上限校验（同时持有未结案案件 ≥ max → 409）
    held = _agent_open_case_count(db, user_id=user.id, tenant_id=tenant_id)
    quota = _claim_quota(db, tenant_id=tenant_id)
    if held >= quota:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_CLAIM_LIMIT",
                "message": f"已达持有上限 {quota} 件，先处理掉部分案件再抢",
            },
        )

    case = db.execute(
        select(CollectionCase).where(CollectionCase.id == case_id).with_for_update()
    ).scalar_one_or_none()
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.pool_type != "public" or case.assigned_to is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_CLAIMED", "message": "案件已被认领或不在公池"},
        )
    case.pool_type = "private"
    case.assigned_to = user.id

    log_audit(
        db,
        actor_user_id=user.id,
        actor_role=role,
        tenant_id=tenant_id,
        action="case.claimed",
        target_type="case",
        target_id=case_id,
        payload={"from": "public_pool"},
    )
    db.commit()
    db.refresh(case)
    return case


@router.post("/cases/{case_id}/release", response_model=CaseResponse)
async def release_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    """v1.6.9 — 催收员把私海案件主动放回公海（仅自己持有的未结案案件可放回）。"""
    tenant_id = _require_tenant(payload)
    role = str(payload.get("role") or "")
    case = db.execute(
        select(CollectionCase).where(CollectionCase.id == case_id).with_for_update()
    ).scalar_one_or_none()
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.assigned_to != user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_YOURS", "message": "只能释放自己持有的案件"},
        )
    if case.stage in ("paid", "closed"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_CLOSED", "message": "已结案案件无需放回公海"},
        )
    case.pool_type = "public"
    case.assigned_to = None

    log_audit(
        db,
        actor_user_id=user.id,
        actor_role=role,
        tenant_id=tenant_id,
        action="case.released",
        target_type="case",
        target_id=case_id,
        payload={"to": "public_pool"},
    )
    db.commit()
    db.refresh(case)
    return case
