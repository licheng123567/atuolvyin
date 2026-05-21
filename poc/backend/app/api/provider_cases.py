"""v0.5.6 — 服务商管理员侧的案件管理 API(PRD §13.x 案件管理)。

诱因:服务商 admin 之前没有任何案件管理入口,案件全部归属物业租户,服务商接外包项目
后只能等物业 admin 分配,自家 supervisor 看,服务商 admin 完全没有调度能力。本期补齐
**只读 + 分配** 这两类操作,够 80% 业务场景(用户已确认)。

业务边界:
- 范围:`Project.provider_id == 本服务商` 的项目下的所有案件(跨租户)
- 操作:列表 / 详情 / 分配 / 重新分配 / 释放回服务商公海;**不允许**改 stage、加跟进备注、
  发缴费链接、创建工单等;这些动作仍走物业 admin 或服务商 supervisor 那一侧
- 分配限制:assign_to 必须是本服务商的员工(UserTenantMembership.provider_id == 本服务商)

端点(全部在 /api/v1/provider 前缀下):
- GET    /cases                          列表(过滤 stage/pool_type/assigned_to/project_id/keyword)
- GET    /cases/{case_id}                详情(复用 build_case_detail_response)
- POST   /cases/assign                   批量分配/重新分配给本服务商员工
- POST   /cases/{case_id}/release        释放回服务商公海(pool_type=public + 清空 assigned_to)

守卫 require_provider_roles("admin");本服务商 supervisor 的「单案件分配/释放」走
supervisor_actions.py 已有路径,不在本模块。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

# build_case_detail_response 与 admin/agent 同源,在 admin_cases.py 是 module-public 函数
from app.api.admin_cases import build_case_detail_response
from app.core.db import get_db
from app.core.phone_visibility import display_owner_phone, should_reveal_owner_phone
from app.core.security import get_token_payload, require_provider_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import ServiceProvider, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.case import (
    CaseAssignRequest,
    CaseAssignResponse,
    CaseDetailResponse,
    CaseWithOwnerResponse,
    OwnerInfo,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

PROVIDER_ADMIN_ROLES = ("admin",)


def _resolve_provider_id(user_id: int, db: Session) -> int:
    """从当前 user 找到所属 provider_id(服务商角色必有 provider_id)。"""
    membership = (
        db.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.user_id == user_id)
            .where(UserTenantMembership.provider_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if membership is None or membership.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_NO_PROVIDER",
                "message": "当前账号未绑定任何服务商",
            },
        )
    return int(membership.provider_id)


def _user_id_from_payload(payload: dict) -> int:
    uid = payload.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token missing user_id"},
        )
    return int(uid)


# ── 列表 ───────────────────────────────────────────────────────────


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_provider_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: str | None = Query(None),
    pool_type: str | None = Query(None),
    assigned_to: int | None = Query(None),
    project_id: int | None = Query(None),
    building: str | None = Query(None),
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    """服务商 admin 案件列表 — 只看本服务商接手项目的案件(跨租户聚合)。"""
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # 核心过滤:Project.provider_id == 本服务商
    # v0.7.0 — LEFT JOIN UserAccount 补 assigned_to_name(原前端只能显 #15)
    #         + 项目名直接 select 出来(原本写死 None,B.2 案件列表要按项目过滤)
    stmt = (
        select(
            CollectionCase,
            OwnerProfile,
            Project.provider_id,
            Project.name.label("project_name"),
            ServiceProvider.name.label("provider_name"),
            UserAccount.name.label("assigned_to_name"),
        )
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id)  # INNER:外包必有项目
        .join(ServiceProvider, ServiceProvider.id == Project.provider_id, isouter=True)
        .join(UserAccount, UserAccount.id == CollectionCase.assigned_to, isouter=True)
        .where(Project.provider_id == provider_id)
    )

    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
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

    # 服务商侧不开放业主手机号明文(隐私边界,合同状态决定);should_reveal_owner_phone 已实现该逻辑
    owner_phone_reveal = should_reveal_owner_phone(role="admin", provider_id=provider_id)

    return PaginatedResponse(
        items=[
            _to_case_response(
                case_obj,
                owner,
                proj_provider_id,
                sp_name,
                owner_phone_reveal=owner_phone_reveal,
                assigned_to_name=assigned_to_name,
                project_name=project_name,
            )
            for case_obj, owner, proj_provider_id, project_name, sp_name, assigned_to_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _to_case_response(
    case_obj: CollectionCase,
    owner: OwnerProfile,
    provider_id: int | None,
    provider_name: str | None,
    *,
    owner_phone_reveal: bool,
    assigned_to_name: str | None = None,  # v0.7.0 A.3
    project_name: str | None = None,  # v0.7.0 B.2 — 不再 N+1,直接 SELECT 出来
) -> CaseWithOwnerResponse:
    """v0.5.6 — 列表行 → CaseWithOwnerResponse(与 admin_cases _case_row_to_response 同形)。"""
    return CaseWithOwnerResponse(
        id=case_obj.id,
        tenant_id=case_obj.tenant_id,
        project_id=case_obj.project_id,
        project_name=project_name,  # v0.7.0 — 已 JOIN Project.name 拿到
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=display_owner_phone(owner.phone_enc, reveal=owner_phone_reveal) or "",
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case_obj.assigned_to,
        assigned_to_name=assigned_to_name,  # v0.7.0
        pool_type=case_obj.pool_type,
        stage=case_obj.stage,
        amount_owed=case_obj.amount_owed,
        months_overdue=case_obj.months_overdue,
        priority_score=case_obj.priority_score,
        last_contact_at=case_obj.last_contact_at,
        monthly_contact_count=case_obj.monthly_contact_count,
        status=case_obj.status,
        notes=case_obj.notes,
        created_at=case_obj.created_at,
        updated_at=case_obj.updated_at,
        provider_id=provider_id,
        provider_name=provider_name,
    )


# ── 详情 ───────────────────────────────────────────────────────────


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_provider_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id)
        .where(
            CollectionCase.id == case_id,
            Project.provider_id == provider_id,
        )
    ).one_or_none()
    if row is None:
        # 注意:故意返回 404 而非 403 — 不告诉调用方「案件存在但你无权」,避免枚举攻击
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不在本服务商范围"},
        )
    case_obj, owner = row[0], row[1]
    return build_case_detail_response(
        db,
        case_obj,
        owner,
        tenant_id=case_obj.tenant_id,
        viewer_role="admin",
        viewer_provider_id=provider_id,
    )


# ── 分配 / 重新分配 ────────────────────────────────────────────────


@router.post("/cases/assign", response_model=CaseAssignResponse)
async def assign_provider_cases(
    body: CaseAssignRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseAssignResponse:
    """批量分配 / 重新分配案件给本服务商员工。

    限制:
    1. 案件必须在本服务商接手项目下(Project.provider_id == 本服务商)
    2. 目标用户必须有本服务商的有效 membership(任意 role,服务商内部自由分)
    """
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    # 1. 验目标用户:本服务商任意 active membership(不限 role,服务商可自由分给 supervisor/agent)
    target_member = db.execute(
        select(UserTenantMembership)
        .where(
            UserTenantMembership.user_id == body.assign_to,
            UserTenantMembership.provider_id == provider_id,
            UserTenantMembership.is_active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()
    if target_member is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_USER_NOT_IN_PROVIDER",
                "message": "目标员工不在本服务商,不能分配",
            },
        )

    # 2. 验所有 case_id 都在本服务商接手项目下;过滤非法的
    valid_case_ids = (
        db.execute(
            select(CollectionCase.id)
            .join(Project, Project.id == CollectionCase.project_id)
            .where(
                CollectionCase.id.in_(body.case_ids),
                Project.provider_id == provider_id,
            )
        )
        .scalars()
        .all()
    )
    valid_set = set(valid_case_ids)
    if len(valid_set) != len(set(body.case_ids)):
        invalid = [c for c in body.case_ids if c not in valid_set]
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_CROSS_PROVIDER",
                "message": f"{len(invalid)} 个案件不在本服务商接手项目内",
            },
        )

    # 3. 批量分配
    stmt = (
        update(CollectionCase)
        .where(CollectionCase.id.in_(valid_set))
        .values(assigned_to=body.assign_to, pool_type="private")
    )
    result = db.execute(stmt)
    db.commit()
    return CaseAssignResponse(updated_count=result.rowcount)


# ── 释放回公海 ────────────────────────────────────────────────────


@router.post("/cases/{case_id}/release", response_model=CaseDetailResponse)
async def release_provider_case_to_pool(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    """把案件从私海释放回服务商公海(清 assigned_to + pool_type='public')。"""
    user_id = _user_id_from_payload(payload)
    provider_id = _resolve_provider_id(user_id, db)

    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id)
        .where(
            CollectionCase.id == case_id,
            Project.provider_id == provider_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不在本服务商范围"},
        )
    case_obj, owner = row[0], row[1]
    case_obj.assigned_to = None
    case_obj.pool_type = "public"
    db.commit()
    db.refresh(case_obj)
    return build_case_detail_response(
        db,
        case_obj,
        owner,
        tenant_id=case_obj.tenant_id,
        viewer_role="admin",
        viewer_provider_id=provider_id,
    )
