from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import (
    get_token_payload,
    require_roles,
    require_tenant_roles,
)
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.case import (
    CaseAssignRequest,
    CaseAssignResponse,
    CaseCallItem,
    CaseDetailResponse,
    CaseImportRequest,
    CaseImportResponse,
    CaseResponse,
    CaseStageUpdate,
    CaseWithOwnerResponse,
    OwnerInfo,
)
from app.schemas.common import PaginatedResponse
from app.services.case_timeline import build_case_timeline
from app.services.payment_link import PaymentLinkOut, build_and_record_payment_link

router = APIRouter()

ADMIN_ROLES = ("admin",)
# v1.4 — 项目经理可读 admin/cases（看自己管的项目案件）但不可写
# v1.5 — 督导可读自己被加入项目的案件
READ_ROLES = ADMIN_ROLES + (
    "project_manager",
    "supervisor",
)


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _calc_priority(amount_owed: Decimal | None, months_overdue: int | None) -> int:
    return int(float(amount_owed or 0) * 0.4 + float(months_overdue or 0) * 0.3)


def _case_row_to_response(
    case: CollectionCase,
    owner: OwnerProfile,
    provider_id: int | None = None,
    provider_name: str | None = None,
    project_name: str | None = None,
    *,
    owner_phone_reveal: bool = False,
) -> CaseWithOwnerResponse:
    """v1.7.0 — owner_phone_reveal 由调用方按角色族 + 合同状态预先决定，避免列表 N+1。"""
    return CaseWithOwnerResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        project_name=project_name,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=display_owner_phone(owner.phone_enc, reveal=owner_phone_reveal) or "",
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        notes=case.notes,
        created_at=case.created_at,
        updated_at=case.updated_at,
        provider_id=provider_id,
        provider_name=provider_name,
    )


def build_case_detail_response(
    db: Session,
    case: CollectionCase,
    owner: OwnerProfile,
    *,
    tenant_id: int,
    include_phone_plain: bool = False,
    viewer_role: str | None = None,
    viewer_provider_id: int | None = None,
    force_owner_phone_reveal: bool = False,
) -> CaseDetailResponse:
    """v1.6.6 — 组装案件详情响应（admin / agent 共用）。

    包含：业主信息 / 通话列表 / 时间线 / 项目信息 / 服务团队（电话+法务）/ 协作来源 role。

    Args:
        include_phone_plain: 仅 agent(internal) 传 True，把手机号明文加入业主信息（用于实际拨号）。
        viewer_role: v1.7.0 — 当前查看者角色，用于 phone_masked 字段动态决定明文/脱敏。
            None 时默认脱敏（兼容老调用方）。
        viewer_provider_id: v1.7.0 — 当前查看者所属服务商 id（仅服务商角色需要），用于查合同状态。
        force_owner_phone_reveal: v1.9.4 — 调用方已自行判定可看明文（如 legal 处理内部订单时），
            跳过 should_reveal_owner_phone 的 stage 校验。
    """
    case_id = case.id
    # 通话列表
    call_rows = db.execute(
        select(CallRecord, UserAccount.name.label("agent_name"))
        .join(UserAccount, UserAccount.id == CallRecord.caller_user_id)
        .where(CallRecord.case_id == case_id, CallRecord.tenant_id == tenant_id)
        .order_by(CallRecord.started_at.desc().nulls_last())
    ).all()
    call_items: list[CaseCallItem] = []
    for call_row in call_rows:
        call = call_row[0]
        agent_name = call_row[1]
        analysis = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call.id)
        ).scalar_one_or_none()
        transcript = db.execute(
            select(Transcript).where(Transcript.call_id == call.id)
        ).scalar_one_or_none()
        confidence = None
        if analysis and analysis.key_segments:
            confidence = analysis.key_segments.get("confidence")
        preview = transcript.full_text[:100] if transcript and transcript.full_text else None
        call_items.append(
            CaseCallItem(
                id=call.id,
                started_at=call.started_at,
                duration_sec=call.duration_sec,
                status=call.status,
                transcript_preview=preview,
                result_tag=call.result_tag,
                confidence=confidence,
                agent_name=agent_name,
                recording_url=call.recording_url,  # v1.6.7 — E5
            )
        )

    # 项目 + 收费 + 合同 + 电话团队
    project_name: str | None = None
    calling_provider_id: int | None = None
    calling_provider_name: str | None = None
    project_info_dict: dict | None = None
    if case.project_id is not None:
        from app.models.case import Project
        from app.models.tenant import ServiceProvider

        proj = db.get(Project, case.project_id)
        if proj is not None:
            project_name = proj.name
            calling_provider_id = proj.provider_id
            if calling_provider_id is not None:
                calling_provider_name = db.execute(
                    select(ServiceProvider.name).where(ServiceProvider.id == calling_provider_id)
                ).scalar_one_or_none()
            project_info_dict = {
                "name": proj.name,
                "charge_rate_text": proj.charge_rate_text,
                "charge_period": proj.charge_period,
                "contract_type": proj.contract_type,
                "contract_start_date": proj.contract_start_date,
                "contract_end_date": proj.contract_end_date,
                "contract_attachment_key": proj.contract_attachment_key,
                "contract_attachment_filename": proj.contract_attachment_filename,
                "charge_notes": proj.charge_notes,
            }

    # 协作来源 role
    # v1.6.10 — 用户可能有多 membership（如督导同时是催收员），优先取 agent 角色（assigned_to 语义）
    assigned_role: str | None = None
    if case.assigned_to is not None:
        m = db.execute(
            select(UserTenantMembership.work_mode)
            .where(
                UserTenantMembership.user_id == case.assigned_to,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "agent",
            )
            .limit(1)
        ).scalar_one_or_none()
        # Preserve old badge format for frontend compatibility; None if not an agent
        assigned_role = f"agent_{m}" if m else None

    # 法务团队（最近一条非 cancelled 的转化订单）
    legal_law_firm_name: str | None = None
    legal_lawyer_name: str | None = None
    legal_order_status: str | None = None
    from app.models.legal_conversion import LegalConversionOrder

    legal_order = (
        db.execute(
            select(LegalConversionOrder)
            .where(
                LegalConversionOrder.case_id == case_id,
                LegalConversionOrder.status != "cancelled",
            )
            .order_by(LegalConversionOrder.created_at.desc())
        )
        .scalars()
        .first()
    )
    if legal_order is not None:
        legal_law_firm_name = legal_order.assigned_law_firm
        legal_lawyer_name = legal_order.assigned_lawyer_name
        legal_order_status = legal_order.status

    # v0.6.0 — 等审批的法务转化申请(状态 pending/pending_admin)。
    # 用于督导端「移交法务 / 审批转法务」按钮条件渲染。
    pending_legal_conversion_request_id: int | None = None
    from app.models.legal_conversion import LegalConversionRequest

    pending_req_id = (
        db.execute(
            select(LegalConversionRequest.id)
            .where(
                LegalConversionRequest.case_id == case_id,
                LegalConversionRequest.status.in_(("pending", "pending_admin")),
            )
            .order_by(LegalConversionRequest.created_at.desc())
        )
        .scalars()
        .first()
    )
    if pending_req_id is not None:
        pending_legal_conversion_request_id = int(pending_req_id)

    # 手机号
    phone_plain = None
    if include_phone_plain:
        from app.core.crypto import decrypt_phone

        phone_plain = decrypt_phone(owner.phone_enc)

    # v1.8.0 — 业主画像 3 统计卡：联系次数复用 monthly_contact_count，承诺/工单各 1 条 COUNT
    from app.models.work import WorkOrder

    promise_count = (
        db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.case_id == case_id,
                CallRecord.tenant_id == tenant_id,
                CallRecord.result_tag == "承诺缴",
            )
        ).scalar_one()
        or 0
    )
    workorder_count = (
        db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.case_id == case_id,
                WorkOrder.tenant_id == tenant_id,
            )
        ).scalar_one()
        or 0
    )

    # v1.7.0 — phone_masked 字段动态：按 viewer 角色族 + 合同 / 项目时效决定明文 / 脱敏
    # v1.9.4 — force_owner_phone_reveal 优先，用于调用方已自行判定的场景
    if force_owner_phone_reveal:
        owner_phone_reveal = True
    elif viewer_role is None:
        owner_phone_reveal = False  # 兼容老调用方
    else:
        from datetime import datetime

        contract_active = is_provider_contract_active(db, tenant_id, viewer_provider_id)
        project_active = True
        if case.project_id is not None:
            from app.models.case import Project as _Project

            _proj = db.get(_Project, case.project_id)
            if _proj is not None and _proj.plan_end is not None:
                project_active = _proj.plan_end >= datetime.now(UTC)
        owner_phone_reveal = should_reveal_owner_phone(
            role=viewer_role,
            provider_id=viewer_provider_id,
            contract_active=contract_active,
            project_active=project_active,
        )

    return CaseDetailResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        project_name=project_name,
        project_info=project_info_dict,  # type: ignore[arg-type]
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone=phone_plain,
            phone_masked=display_owner_phone(owner.phone_enc, reveal=owner_phone_reveal) or "",
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        assigned_role=assigned_role,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        bill_period_start=case.bill_period_start,
        bill_period_end=case.bill_period_end,
        principal_amount=case.principal_amount,
        late_fee_amount=case.late_fee_amount,
        arrears_reason=case.arrears_reason,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        promise_count=promise_count,
        workorder_count=workorder_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        calls=call_items,
        timeline_events=build_case_timeline(db, case_id, tenant_id),
        calling_provider_id=calling_provider_id,
        calling_provider_name=calling_provider_name,
        legal_law_firm_name=legal_law_firm_name,
        legal_lawyer_name=legal_lawyer_name,
        legal_order_status=legal_order_status,
        pending_legal_conversion_request_id=pending_legal_conversion_request_id,
    )


@router.post("/cases/import", response_model=CaseImportResponse, status_code=201)
async def import_cases(
    body: CaseImportRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseImportResponse:
    tenant_id = _require_tenant(payload)

    # 校验 project_id 属本租户
    project_agent_ids: list[int] = []
    if body.project_id is not None:
        from app.models.case import Project
        from app.models.project_member import ProjectMember

        project = db.execute(
            select(Project).where(
                Project.id == body.project_id,
                Project.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if project is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_INVALID_PROJECT", "message": "项目不存在或不属本租户"},
            )
        # v1.5 S18.5 — 取项目的默认催收员，导入时 round-robin 分配
        project_agent_ids = list(
            db.execute(
                select(ProjectMember.user_id)
                .where(
                    ProjectMember.project_id == body.project_id,
                    ProjectMember.role_in_project == "agent",
                    ProjectMember.is_active.is_(True),
                )
                .order_by(ProjectMember.id)
            )
            .scalars()
            .all()
        )

    imported = 0
    for idx, row in enumerate(body.rows):
        existing_owner = db.execute(
            select(OwnerProfile).where(
                OwnerProfile.tenant_id == tenant_id,
                OwnerProfile.phone_enc == encrypt_phone(row.phone),
            )
        ).scalar_one_or_none()

        if existing_owner is None:
            owner = OwnerProfile(
                tenant_id=tenant_id,
                name=row.name,
                phone_enc=encrypt_phone(row.phone),
                building=row.building,
                room=row.room,
            )
            db.add(owner)
            db.flush()
        else:
            owner = existing_owner

        # v1.5 S18.5 — round-robin 分配给项目的默认催收员
        assigned_to: int | None = None
        pool_type = "public"
        if project_agent_ids:
            assigned_to = project_agent_ids[idx % len(project_agent_ids)]
            pool_type = "private"

        case = CollectionCase(
            tenant_id=tenant_id,
            project_id=body.project_id,
            owner_id=owner.id,
            assigned_to=assigned_to,
            pool_type=pool_type,
            stage="new",
            amount_owed=row.amount_owed,
            months_overdue=row.months_overdue,
            priority_score=_calc_priority(row.amount_owed, row.months_overdue),
            notes=row.notes,
            # v1.6.3 — 账单字段从导入直接录入，不再按月推算
            bill_period_start=row.bill_period_start,
            bill_period_end=row.bill_period_end,
            principal_amount=row.principal_amount,
            late_fee_amount=row.late_fee_amount,
            arrears_reason=row.arrears_reason,
        )
        db.add(case)
        imported += 1

    db.flush()
    db.commit()
    return CaseImportResponse(imported=imported, skipped=0, errors=[])


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: str | None = Query(None),
    pool_type: str | None = Query(None),
    assigned_to: int | None = Query(None),
    project_id: int | None = Query(None),
    provider_id: int | None = Query(None),
    building: str | None = Query(None),
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    from app.models.case import Project
    from app.models.tenant import ServiceProvider

    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")
    user_id = int(payload.get("user_id") or 0)

    stmt = (
        select(CollectionCase, OwnerProfile, Project.provider_id, ServiceProvider.name)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id, isouter=True)
        .join(ServiceProvider, ServiceProvider.id == Project.provider_id, isouter=True)
        .where(CollectionCase.tenant_id == tenant_id)
    )

    # v1.5 S18.5 — 督导只看自己被加入项目的案件
    if role == "supervisor":
        from app.models.project_member import ProjectMember

        visible_project_ids = list(
            db.execute(
                select(ProjectMember.project_id).where(
                    ProjectMember.user_id == user_id,
                    ProjectMember.role_in_project == "supervisor",
                    ProjectMember.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not visible_project_ids:
            # 无项目归属 — 返回空集
            stmt = stmt.where(CollectionCase.id == -1)
        else:
            stmt = stmt.where(CollectionCase.project_id.in_(visible_project_ids))

    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if provider_id is not None:
        stmt = stmt.where(Project.provider_id == provider_id)
    if building:
        stmt = stmt.where(OwnerProfile.building == building)
    if keyword:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CollectionCase.priority_score.desc(), CollectionCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # v1.7.0 — admin/PM/supervisor 都属物业内部，永远明文；列表层一次决策复用
    owner_phone_reveal = should_reveal_owner_phone(role=role, provider_id=payload.get("provider_id"))

    return PaginatedResponse(
        items=[
            _case_row_to_response(
                case, owner, prov_id, prov_name, owner_phone_reveal=owner_phone_reveal
            )
            for case, owner, prov_id, prov_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/buildings")
async def list_distinct_buildings(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    project_id: int | None = Query(None),
) -> list[str]:
    """返回本租户去重后的楼栋列表，按 project_id 过滤。"""
    tenant_id = _require_tenant(payload)
    stmt = (
        select(OwnerProfile.building)
        .join(CollectionCase, CollectionCase.owner_id == OwnerProfile.id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            OwnerProfile.building.isnot(None),
        )
        .distinct()
    )
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    rows = db.execute(stmt.order_by(OwnerProfile.building)).scalars().all()
    return [b for b in rows if b]


@router.post("/cases/assign", response_model=CaseAssignResponse)
async def assign_cases(
    body: CaseAssignRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseAssignResponse:
    tenant_id = _require_tenant(payload)

    # v1.6.10 — 用户可能有多个 membership（如督导兼催收员）；分配只看 internal agent 那条
    member = db.execute(
        select(UserTenantMembership)
        .where(
            UserTenantMembership.user_id == body.assign_to,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
            UserTenantMembership.role == "agent",
            UserTenantMembership.work_mode == "internal",
        )
        .limit(1)
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_USER_NOT_IN_TENANT", "message": "指定用户不在本租户"},
        )

    # v1.5.6 — 组织边界：物业 admin 只能分给内部催收员（work_mode=internal）；外勤由服务商内部分配
    if member.work_mode != "internal":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_NOT_INTERNAL_AGENT",
                "message": "物业 admin 仅可分配给内部催收员；外勤请由服务商管理",
            },
        )

    # v1.5.6 收尾 — 组织边界硬约束：外包项目（有 provider_id）一律由服务商内部分配
    # 砍掉 allow_internal_assist 例外（项目要么自办要么外包，二选一）
    from app.models.case import Project

    bad_cases = db.execute(
        select(CollectionCase.id)
        .join(Project, Project.id == CollectionCase.project_id, isouter=True)
        .where(
            CollectionCase.id.in_(body.case_ids),
            CollectionCase.tenant_id == tenant_id,
            Project.provider_id.is_not(None),
        )
    ).all()
    if bad_cases:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_OUTSOURCED_PROJECT",
                "message": (
                    f"{len(bad_cases)} 个案件属外包项目，由服务商内部分配。"
                    "若要由物业自办，请将项目「合作服务商」改为空。"
                ),
            },
        )

    stmt = (
        update(CollectionCase)
        .where(
            CollectionCase.id.in_(body.case_ids),
            CollectionCase.tenant_id == tenant_id,
        )
        .values(assigned_to=body.assign_to, pool_type="private")
    )
    result = db.execute(stmt)
    db.commit()
    return CaseAssignResponse(updated_count=result.rowcount)


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
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
    role = payload.get("role", "")
    return build_case_detail_response(
        db,
        case,
        owner,
        tenant_id=tenant_id,
        viewer_role=role,
        viewer_provider_id=payload.get("provider_id"),
    )


@router.patch("/cases/{case_id}/stage", response_model=CaseResponse)
async def update_case_stage(
    case_id: int,
    body: CaseStageUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    # v1.6.10 — supervisor 详情页跟进备注复用此 endpoint
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES, "supervisor"))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    prev_stage = case.stage
    case.stage = body.stage
    db.commit()
    db.refresh(case)
    # v1.6.6 — 阶段变更写 audit log（含跟进备注）
    from app.services.audit import log_audit

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0),
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
    # Sprint 15.4b — case_escalated 通知：进入 escalated/legal 阶段时触发
    _ESCALATED_STAGES = {"escalated", "legal", "litigation"}
    if body.stage in _ESCALATED_STAGES and prev_stage not in _ESCALATED_STAGES:
        from app.models.case import OwnerProfile
        from app.services.notifications.event_subscribers import notify_case_escalated

        owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
        notify_case_escalated(
            db,
            tenant_id=int(case.tenant_id),
            case_id=int(case.id),
            owner_name=owner.name if owner else None,
            new_stage=body.stage,
            operator_user_id=int(payload.get("user_id") or 0) or None,
        )
        db.commit()
    return case


@router.post(
    "/cases/{case_id}/send-payment-link",
    response_model=PaymentLinkOut,
    status_code=201,
)
def admin_send_payment_link(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[
        UserAccount, Depends(require_tenant_roles("admin", "supervisor"))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> PaymentLinkOut:
    """v2.2 — 物业管理端发送缴费链接。

    与坐席端（/agent/cases/{id}/send-payment-link）共用生成逻辑，区别在于：
    管理员 / 督导可对本租户任意案件发送，不要求 assigned_to == 自己 —— 便于把
    缴费二维码 / 短链转给催收人员通过微信发给业主。
    """
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    if not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_OWNER_MISSING", "message": "案件未关联业主"},
        )
    return build_and_record_payment_link(
        db,
        case=case,
        owner=owner,
        actor_user_id=int(payload.get("user_id") or 0),
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
    )
