"""Sprint 16.2 — admin projects router (物业项目 CRUD).

Endpoints:
    GET    /api/v1/admin/projects             list
    POST   /api/v1/admin/projects             create
    GET    /api/v1/admin/projects/{id}        detail
    PATCH  /api/v1/admin/projects/{id}        update
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, Project
from app.models.tenant import ServiceProvider, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreateIn, ProjectOut, ProjectUpdateIn
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")


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
) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        project_type=p.project_type,
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
    )


def _enrich(db: Session, p: Project) -> ProjectOut:
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
    return _to_out(p, case_count, provider_name, property_pm_name, provider_pm_name)


@router.get("/projects", response_model=PaginatedResponse[ProjectOut])
def list_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
) -> PaginatedResponse[ProjectOut]:
    tenant_id = _require_tenant(payload)
    stmt = select(Project).where(Project.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = db.execute(
        stmt.order_by(Project.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    items = [_enrich(db, p) for p in rows]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post(
    "/projects",
    response_model=ProjectOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_project(
    body: ProjectCreateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)

    # 校验 PM 用户属于本租户
    if body.property_pm_user_id:
        m = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == body.property_pm_user_id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "project_manager_property",
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

    p = Project(
        tenant_id=tenant_id,
        name=body.name,
        project_type=body.project_type,
        provider_id=body.provider_id,
        property_pm_user_id=body.property_pm_user_id,
        provider_pm_user_id=body.provider_pm_user_id,
        plan_start=body.plan_start,
        plan_end=body.plan_end,
        description=body.description,
        allow_internal_assist=body.allow_internal_assist,
        status="active",
    )
    db.add(p)
    db.flush()
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="project.created",
        target_type="project",
        target_id=p.id,
        payload={"name": p.name, "provider_id": p.provider_id},
    )
    db.commit()
    db.refresh(p)
    return _enrich(db, p)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)
    p = db.execute(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == tenant_id
        )
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
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    tenant_id = _require_tenant(payload)
    p = db.execute(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在"},
        )

    data = body.model_dump(exclude_unset=True)
    old_provider_id = p.provider_id
    for field, value in data.items():
        setattr(p, field, value)

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
    db.commit()
    db.refresh(p)
    return _enrich(db, p)
