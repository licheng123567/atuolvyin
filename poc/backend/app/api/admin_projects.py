"""Sprint 16.2 — admin projects router (物业项目 CRUD).

Endpoints:
    GET    /api/v1/admin/projects             list
    POST   /api/v1/admin/projects             create
    GET    /api/v1/admin/projects/{id}        detail
    PATCH  /api/v1/admin/projects/{id}        update
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.case import CollectionCase, Project
from app.models.tenant import ServiceProvider, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreateIn, ProjectOut, ProjectUpdateIn
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")
# v1.9.7 — 法务 / 协调员 / 督导也可读项目列表（用于「按项目过滤」下拉框）
PROJECT_LIST_ROLES = ADMIN_ROLES + ("legal", "coordinator", "workorder", "supervisor")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _to_out(
    p: Project,
    case_count: int,
    provider_name: str | None,
    property_pm_name: str | None,
    provider_pm_name: str | None,
    coordinator_user_id: int | None = None,
    coordinator_name: str | None = None,
    legal_user_id: int | None = None,
    legal_name: str | None = None,
) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        provider_id=p.provider_id,
        provider_name=provider_name,
        property_pm_user_id=p.property_pm_user_id,
        property_pm_name=property_pm_name,
        provider_pm_user_id=p.provider_pm_user_id,
        provider_pm_name=provider_pm_name,
        plan_start=p.plan_start,
        plan_end=p.plan_end,
        status=p.status,
        description=p.description,
        allow_internal_assist=p.allow_internal_assist,
        case_count=case_count,
        created_at=p.created_at,
        coordinator_user_id=coordinator_user_id,
        coordinator_name=coordinator_name,
        legal_user_id=legal_user_id,
        legal_name=legal_name,
        # v1.6 — 收费 + 合同
        charge_rate_per_sqm=p.charge_rate_per_sqm,
        charge_rate_text=p.charge_rate_text,
        charge_period=p.charge_period,
        contract_type=p.contract_type,
        contract_start_date=p.contract_start_date,
        contract_end_date=p.contract_end_date,
        contract_attachment_key=p.contract_attachment_key,
        contract_attachment_filename=p.contract_attachment_filename,
        charge_notes=p.charge_notes,
        # v1.6.1 — 项目级「本金打折」阈值
        discount_auto_approve_threshold_pct=p.discount_auto_approve_threshold_pct,
        discount_supervisor_max_pct=p.discount_supervisor_max_pct,
        discount_disabled=p.discount_disabled,
        # v1.6.2 — 项目级「滞纳金减免」阈值
        late_fee_waive_auto_approve_threshold_pct=p.late_fee_waive_auto_approve_threshold_pct,
        late_fee_waive_supervisor_max_pct=p.late_fee_waive_supervisor_max_pct,
        late_fee_waive_disabled=p.late_fee_waive_disabled,
        # §9.2 D1/D2 — 项目级佣金率
        internal_agent_commission_rate=p.internal_agent_commission_rate,
        provider_agent_commission_rate=p.provider_agent_commission_rate,
        # v2.2 — 项目级收款配置
        payment_mode=p.payment_mode,
        payee_name=p.payee_name,
        payee_account=p.payee_account,
        payee_qr_object_key=p.payee_qr_object_key,
        payment_instructions=p.payment_instructions,
    )


def _enrich(db: Session, p: Project) -> ProjectOut:
    from app.models.project_member import ProjectMember

    case_count = db.execute(
        select(func.count(CollectionCase.id)).where(
            CollectionCase.tenant_id == p.tenant_id,
            CollectionCase.project_id == p.id,
        )
    ).scalar_one()
    provider_name = None
    if p.provider_id:
        provider_name = db.execute(
            select(ServiceProvider.name).where(ServiceProvider.id == p.provider_id)
        ).scalar_one_or_none()
    property_pm_name = None
    if p.property_pm_user_id:
        property_pm_name = db.execute(
            select(UserAccount.name).where(UserAccount.id == p.property_pm_user_id)
        ).scalar_one_or_none()
    provider_pm_name = None
    if p.provider_pm_user_id:
        provider_pm_name = db.execute(
            select(UserAccount.name).where(UserAccount.id == p.provider_pm_user_id)
        ).scalar_one_or_none()

    # v1.5.6 — 协调员 + 法务对接人（从 project_member 表读 active 行）
    def _read_member(role: str) -> tuple[int | None, str | None]:
        row = db.execute(
            select(ProjectMember.user_id, UserAccount.name)
            .join(UserAccount, UserAccount.id == ProjectMember.user_id)
            .where(
                ProjectMember.project_id == p.id,
                ProjectMember.role_in_project == role,
                ProjectMember.is_active.is_(True),
            )
            .limit(1)
        ).one_or_none()
        return (row[0], row[1]) if row else (None, None)

    coord_uid, coord_name = _read_member("coordinator")
    legal_uid, legal_name = _read_member("legal")
    return _to_out(
        p,
        case_count,
        provider_name,
        property_pm_name,
        provider_pm_name,
        coordinator_user_id=coord_uid,
        coordinator_name=coord_name,
        legal_user_id=legal_uid,
        legal_name=legal_name,
    )


@router.get("/projects", response_model=PaginatedResponse[ProjectOut])
def list_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*PROJECT_LIST_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    provider_id: int | None = Query(None),
) -> PaginatedResponse[ProjectOut]:
    tenant_id = _require_tenant(payload)
    stmt = select(Project).where(Project.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if provider_id is not None:
        stmt = stmt.where(Project.provider_id == provider_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Project.id.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    items = [_enrich(db, p) for p in rows]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/projects",
    response_model=ProjectOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_project(
    body: ProjectCreateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)

    # 校验 PM 用户属于本租户
    if body.property_pm_user_id:
        m = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == body.property_pm_user_id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "project_manager",
                UserTenantMembership.provider_id.is_(None),  # property-side PM only
            )
        ).scalar_one_or_none()
        if m is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_INVALID_PM", "message": "项目负责人(物业)不存在"},
            )

    if body.provider_id:
        sp = db.execute(
            select(ServiceProvider).where(
                ServiceProvider.id == body.provider_id,
                ServiceProvider.audit_status == "approved",
            )
        ).scalar_one_or_none()
        if sp is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_INVALID_PROVIDER", "message": "服务商不存在或未审核通过"},
            )

    # v1.5.6 — 组织边界硬约束：项目要么自办、要么外包，二选一
    is_outsourced = body.provider_id is not None
    if is_outsourced and (body.supervisor_user_ids or body.agent_user_ids):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_OUTSOURCED_NO_INTERNAL_TEAM",
                "message": "外包项目不应指派物业内部督导/催收员；他们由服务商内部决定",
            },
        )
    # v1.5.6 — 任意项目都必须指定协调员 + 法务对接人
    if body.coordinator_user_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_MISSING_COORDINATOR",
                "message": "请指定 1 名物业协调员（接此项目的工单）",
            },
        )
    if body.legal_user_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_MISSING_LEGAL",
                "message": "请指定 1 名法务对接人（处理此项目的法务转化）",
            },
        )

    p = Project(
        tenant_id=tenant_id,
        name=body.name,
        provider_id=body.provider_id,
        property_pm_user_id=body.property_pm_user_id,
        # v1.5.6 — 服务商 PM 由服务商端指派；物业 admin 此处一律 NULL
        provider_pm_user_id=None,
        plan_start=body.plan_start,
        plan_end=body.plan_end,
        description=body.description,
        allow_internal_assist=False,  # v1.5.6 — 已废弃，强制 False
        status="active",
        # v1.6 — 收费 + 合同
        charge_rate_per_sqm=body.charge_rate_per_sqm,
        charge_rate_text=body.charge_rate_text,
        charge_period=body.charge_period,
        contract_type=body.contract_type,
        contract_start_date=body.contract_start_date,
        contract_end_date=body.contract_end_date,
        contract_attachment_key=body.contract_attachment_key,
        contract_attachment_filename=body.contract_attachment_filename,
        charge_notes=body.charge_notes,
        # v1.6.1 — 项目级「本金打折」阈值
        discount_auto_approve_threshold_pct=body.discount_auto_approve_threshold_pct,
        discount_supervisor_max_pct=body.discount_supervisor_max_pct,
        discount_disabled=body.discount_disabled,
        # v1.6.2 — 项目级「滞纳金减免」阈值
        late_fee_waive_auto_approve_threshold_pct=body.late_fee_waive_auto_approve_threshold_pct,
        late_fee_waive_supervisor_max_pct=body.late_fee_waive_supervisor_max_pct,
        late_fee_waive_disabled=body.late_fee_waive_disabled,
        # §9.2-D1 — 项目级内勤佣金率
        internal_agent_commission_rate=body.internal_agent_commission_rate,
        # §9.2-D2 — 外包项目的服务商坐席佣金率初始值
        provider_agent_commission_rate=body.provider_agent_commission_rate,
        # v2.2 — 项目级收款配置
        payee_name=body.payee_name,
        payee_account=body.payee_account,
        payee_qr_object_key=body.payee_qr_object_key,
        payment_instructions=body.payment_instructions,
    )
    db.add(p)
    db.flush()

    # v1.5 S18.5 — 写入项目团队成员（督导 + 催收员 + v1.5.6 协调员）
    from app.models.project_member import ProjectMember

    def _validate_member_role(uid: int, expected_role: str) -> None:
        m = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == uid,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.is_active.is_(True),
                UserTenantMembership.role == expected_role,
            )
        ).scalar_one_or_none()
        if m is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ERR_INVALID_MEMBER",
                    "message": f"用户 {uid} 不是 {expected_role} 角色或不属本租户",
                },
            )

    # v1.5.6 — 任意项目都写入 coordinator + legal 绑定
    _validate_member_role(body.coordinator_user_id, "coordinator")  # type: ignore[arg-type]
    db.add(
        ProjectMember(
            project_id=p.id,
            user_id=body.coordinator_user_id,
            role_in_project="coordinator",
        )
    )
    _validate_member_role(body.legal_user_id, "legal")  # type: ignore[arg-type]
    db.add(
        ProjectMember(
            project_id=p.id,
            user_id=body.legal_user_id,
            role_in_project="legal",
        )
    )

    # 自办：额外写入督导 + 催收员
    if not is_outsourced:
        for uid in body.supervisor_user_ids:
            _validate_member_role(uid, "supervisor")
            db.add(
                ProjectMember(
                    project_id=p.id,
                    user_id=uid,
                    role_in_project="supervisor",
                )
            )
        for uid in body.agent_user_ids:
            _validate_member_role(uid, "agent")
            db.add(
                ProjectMember(
                    project_id=p.id,
                    user_id=uid,
                    role_in_project="agent",
                )
            )

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="project.created",
        target_type="project",
        target_id=p.id,
        payload={
            "name": p.name,
            "provider_id": p.provider_id,
            "is_outsourced": is_outsourced,
            "coordinator_user_id": body.coordinator_user_id if is_outsourced else None,
            "supervisor_count": 0 if is_outsourced else len(body.supervisor_user_ids),
            "agent_count": 0 if is_outsourced else len(body.agent_user_ids),
        },
    )
    db.commit()
    db.refresh(p)
    return _enrich(db, p)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)
    p = db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在"},
        )
    return _enrich(db, p)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)
    p = db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在"},
        )

    data = body.model_dump(exclude_unset=True)
    # v1.5.6 — 物业 admin 不允许直接改 provider_pm_user_id（由服务商端指派）
    data.pop("provider_pm_user_id", None)
    # v1.5.6 — allow_internal_assist 已废弃，物业 admin 不可改
    data.pop("allow_internal_assist", None)
    # v1.5.6 — coordinator_user_id / legal_user_id 走 ProjectMember 表，不直接写到 Project
    new_coordinator = data.pop("coordinator_user_id", None)
    new_legal = data.pop("legal_user_id", None)

    old_provider_id = p.provider_id
    old_plan_end = p.plan_end
    for field, value in data.items():
        setattr(p, field, value)

    # v1.5.6 — coordinator + legal 绑定 reconcile（任意项目）
    from sqlalchemy import update as sa_update

    from app.models.project_member import ProjectMember

    def _reconcile_member(new_uid: int | None, role_in_project: str, expected_role: str) -> None:
        if new_uid is None:
            return
        m = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == new_uid,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == expected_role,
                UserTenantMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if m is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": f"ERR_INVALID_{role_in_project.upper()}",
                    "message": f"用户 {new_uid} 不是 {expected_role} 或不属本租户",
                },
            )
        db.execute(
            sa_update(ProjectMember)
            .where(
                ProjectMember.project_id == p.id,
                ProjectMember.role_in_project == role_in_project,
                ProjectMember.is_active.is_(True),
                ProjectMember.user_id != new_uid,
            )
            .values(is_active=False)
        )
        existing = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == p.id,
                ProjectMember.user_id == new_uid,
                ProjectMember.role_in_project == role_in_project,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                ProjectMember(
                    project_id=p.id,
                    user_id=new_uid,
                    role_in_project=role_in_project,
                )
            )
        elif not existing.is_active:
            existing.is_active = True

    _reconcile_member(new_coordinator, "coordinator", "coordinator")
    _reconcile_member(new_legal, "legal", "legal")

    # 服务商变更专门记审计（业务关键）
    if "provider_id" in data and old_provider_id != p.provider_id:
        log_audit(
            db,
            actor_user_id=int(payload.get("user_id") or 0) or None,
            actor_role=payload.get("role"),
            tenant_id=tenant_id,
            action="project.provider.assigned",
            target_type="project",
            target_id=p.id,
            payload={
                "old_provider_id": old_provider_id,
                "new_provider_id": p.provider_id,
            },
        )
    # v1.5.5 — 服务期变更（延长 / 调整）专门记审计
    if "plan_end" in data and old_plan_end != p.plan_end:
        log_audit(
            db,
            actor_user_id=int(payload.get("user_id") or 0) or None,
            actor_role=payload.get("role"),
            tenant_id=tenant_id,
            action="project.extended"
            if (p.plan_end and old_plan_end and p.plan_end > old_plan_end)
            else "project.plan_end_changed",
            target_type="project",
            target_id=p.id,
            payload={
                "old_plan_end": old_plan_end.isoformat() if old_plan_end else None,
                "new_plan_end": p.plan_end.isoformat() if p.plan_end else None,
            },
        )
    db.commit()
    db.refresh(p)
    return _enrich(db, p)


# v1.6.2 — 合同 PDF 上传 ───────────────────────────────────────────
MAX_CONTRACT_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_CONTRACT_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/projects/contract/upload")
async def upload_project_contract(
    file: UploadFile = File(...),
    payload: Annotated[dict, Depends(get_token_payload)] = ...,
    _admin: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES))] = ...,
) -> dict:
    """物业 admin 上传项目合同（创建/编辑项目时使用），返回 object_key + filename。

    前端拿到 object_key 后随表单提交一并保存到 project.contract_attachment_key。
    """
    import uuid

    from app.core.storage import storage

    tenant_id = _require_tenant(payload)
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_CONTRACT_MIMES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_MIME", "message": f"不支持的合同文件类型：{mime}"},
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_EMPTY_FILE", "message": "上传文件为空"},
        )
    if len(raw) > MAX_CONTRACT_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "ERR_FILE_TOO_LARGE", "message": "合同文件超过 20MB 限制"},
        )

    filename = file.filename or f"contract_{uuid.uuid4().hex[:8]}.pdf"
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
    object_key = f"contracts/{tenant_id}/{uuid.uuid4().hex}.{ext}"
    try:
        storage.put_object(object_key, raw, mime)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "文件存储失败"},
        ) from exc

    return {
        "object_key": object_key,
        "filename": filename,
        "size_bytes": len(raw),
        "mime_type": mime,
    }


@router.get("/projects/contract/url")
def get_project_contract_url(
    object_key: str = Query(..., description="合同 object_key"),
    _admin: Annotated[UserAccount, Depends(require_tenant_roles(*ADMIN_ROLES))] = ...,
) -> dict:
    """换取合同临时下载 URL（前端预览/下载用）。"""
    from app.core.storage import storage

    return {"url": storage.get_url(object_key)}
