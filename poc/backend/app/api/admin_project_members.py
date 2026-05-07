"""v1.5 S18.5 — 项目团队成员管理（admin 端）。

端点：
    GET    /api/v1/admin/projects/{id}/members
    POST   /api/v1/admin/projects/{id}/members      — 批量加入
    DELETE /api/v1/admin/projects/{id}/members/{user_id}
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import Project
from app.models.project_member import ProjectMember
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")


class ProjectMemberItem(BaseModel):
    user_id: int
    name: str
    role_in_project: str  # supervisor | agent
    membership_role: str  # supervisor | agent_internal
    is_active: bool


class AddMembersIn(BaseModel):
    members: list["AddMemberItem"] = Field(..., min_length=1)


class AddMemberItem(BaseModel):
    user_id: int
    role_in_project: Literal["supervisor", "agent"]


AddMembersIn.model_rebuild()


def _require_tenant_project(
    db: Session, payload: dict, project_id: int
) -> Project:
    tid = payload.get("tenant_id")
    if not tid:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    p = db.execute(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == int(tid)
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "项目不存在"},
        )
    return p


@router.get(
    "/projects/{project_id}/members",
    response_model=list[ProjectMemberItem],
)
def list_members(
    project_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectMemberItem]:
    p = _require_tenant_project(db, payload, project_id)
    rows = db.execute(
        select(ProjectMember, UserAccount, UserTenantMembership)
        .join(UserAccount, UserAccount.id == ProjectMember.user_id)
        .join(
            UserTenantMembership,
            (UserTenantMembership.user_id == UserAccount.id)
            & (UserTenantMembership.tenant_id == p.tenant_id),
        )
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.role_in_project, ProjectMember.id)
    ).all()
    return [
        ProjectMemberItem(
            user_id=u.id,
            name=u.name,
            role_in_project=pm.role_in_project,
            membership_role=m.role,
            is_active=pm.is_active and m.is_active,
        )
        for pm, u, m in rows
    ]


@router.post(
    "/projects/{project_id}/members",
    status_code=http_status.HTTP_201_CREATED,
)
def add_members(
    project_id: int,
    body: AddMembersIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    p = _require_tenant_project(db, payload, project_id)

    expected_membership_role = {
        "supervisor": "supervisor",
        "agent": "agent_internal",
    }

    added = 0
    for item in body.members:
        m = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == item.user_id,
                UserTenantMembership.tenant_id == p.tenant_id,
                UserTenantMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if m is None or m.role != expected_membership_role[item.role_in_project]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ERR_INVALID_MEMBER",
                    "message": (
                        f"用户 {item.user_id} 不是 {expected_membership_role[item.role_in_project]}"
                        f" 角色或不属本租户"
                    ),
                },
            )
        try:
            db.add(ProjectMember(
                project_id=project_id,
                user_id=item.user_id,
                role_in_project=item.role_in_project,
            ))
            db.flush()
            added += 1
        except IntegrityError:
            db.rollback()
            # 已存在，忽略
            pass
    db.commit()
    return {"added": added}


@router.delete(
    "/projects/{project_id}/members/{user_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def remove_member(
    project_id: int,
    user_id: int,
    role_in_project: Literal["supervisor", "agent"],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _require_tenant_project(db, payload, project_id)
    pm = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role_in_project == role_in_project,
        )
    ).scalar_one_or_none()
    if pm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "成员不存在"},
        )
    db.delete(pm)
    db.commit()
