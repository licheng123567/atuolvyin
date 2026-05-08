from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.crypto import decrypt_phone, encrypt_phone
from app.core.db import get_db
from app.core.security import (
    get_password_hash,
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.device import DeviceProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    UserCreateByAdminRequest,
    UserListResponse,
    UserOtpIssueOut,
    UserUpdateByAdminRequest,
)


class AdminDeviceItem(BaseModel):
    device_id: str
    user_id: int
    brand: str | None = None
    model: str | None = None
    os_version: str | None = None
    push_reg_id_set: bool
    push_provider: str | None = None
    is_healthy: bool
    last_check_at: datetime | None = None
    created_at: datetime

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _user_to_response(user: UserAccount, role: str) -> UserListResponse:
    return UserListResponse(
        id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserListResponse]:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    # v1.5.6 — 一人多角色：先取去重 user_id 集（每行 1 个用户），再聚合 roles
    user_stmt = (
        select(UserAccount.id)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
        .distinct()
    )
    if q:
        user_stmt = user_stmt.where(UserAccount.name.ilike(f"%{q}%"))

    count_stmt = select(func.count()).select_from(user_stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    user_ids = list(db.execute(
        user_stmt.order_by(UserAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all())

    if not user_ids:
        return PaginatedResponse(items=[], total=total, page=page, page_size=page_size)

    # 聚合：每个 user_id 拉所有 roles
    rows = db.execute(
        select(UserAccount, UserTenantMembership.role)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id.in_(user_ids),
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).all()

    user_map: dict[int, tuple[UserAccount, list[str]]] = {}
    for user, role in rows:
        if user.id not in user_map:
            user_map[user.id] = (user, [])
        user_map[user.id][1].append(role)

    items = []
    for uid in user_ids:
        if uid not in user_map:
            continue
        user, roles = user_map[uid]
        primary_role = roles[0]
        resp = _user_to_response(user, primary_role)
        resp.all_roles = roles
        items.append(resp)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserListResponse)
async def get_user(
    user_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    """v1.5.5 — 单用户详情，给 admin/users/{id}/edit 用。"""
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    rows = db.execute(
        select(UserAccount, UserTenantMembership.role)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).all()
    if not rows:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    target = rows[0][0]
    roles = [r[1] for r in rows]
    response = _user_to_response(target, roles[0])
    response.email = target.email
    response.last_login_at = target.last_login_at
    response.login_method = target.login_method
    response.all_roles = roles
    return response


@router.post("/users", response_model=UserListResponse, status_code=201)
async def create_user(
    body: UserCreateByAdminRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    # v1.4 方案 A — 未指定密码时占位 hash（不可登录）；员工首次登录走 OTP
    import secrets

    # v1.5.6 — 检测是否手机号已注册：若已是其他角色（跨组织/跨租户）则追加 membership
    phone_enc_val = encrypt_phone(body.phone)
    existing_user = db.execute(
        select(UserAccount).where(UserAccount.phone_enc == phone_enc_val)
    ).scalar_one_or_none()

    if existing_user is not None:
        # 检查本租户内是否已有 active membership（同租户重复 = 真重复）
        existing_membership = db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == existing_user.id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if existing_membership is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "code": "ERR_DUPLICATE_IN_TENANT",
                    "message": (
                        f"此手机号在本租户已有角色 {existing_membership.role}，"
                        "请直接编辑现有用户，无需重复创建。"
                    ),
                },
            )
        # 跨组织员工：复用 UserAccount，只追加 membership
        membership = UserTenantMembership(
            user_id=existing_user.id,
            tenant_id=tenant_id,
            role=body.role,
            source_type="INTERNAL",
            is_active=True,
        )
        db.add(membership)
        db.commit()
        db.refresh(existing_user)
        new_user = existing_user
        login_method = existing_user.login_method or "otp"
    else:
        if body.password:
            pw_hash = get_password_hash(body.password)
            login_method = "phone"
        else:
            # 64 字节随机 token + bcrypt → 实际不可命中；员工只能用 OTP 登录
            pw_hash = get_password_hash(secrets.token_urlsafe(48))
            login_method = "otp"

        new_user = UserAccount(
            phone_enc=phone_enc_val,
            name=body.name,
            password_hash=pw_hash,
            login_method=login_method,
            is_active=True,
        )
        db.add(new_user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={"code": "ERR_DUPLICATE_PHONE", "message": "手机号已被注册"},
            ) from None

        membership = UserTenantMembership(
            user_id=new_user.id,
            tenant_id=tenant_id,
            role=body.role,
            source_type="INTERNAL",
            is_active=True,
        )
        db.add(membership)
        db.commit()
        db.refresh(new_user)

    # v1.5.6 — 一人多角色：追加 extra_roles 对应的 membership（去重，跳过已存在）
    all_roles = [body.role]
    extra = [r for r in (body.extra_roles or []) if r and r != body.role]
    if extra:
        existing_roles = set(db.execute(
            select(UserTenantMembership.role).where(
                UserTenantMembership.user_id == new_user.id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.is_active.is_(True),
            )
        ).scalars().all())
        for r in extra:
            if r in existing_roles:
                continue
            db.add(UserTenantMembership(
                user_id=new_user.id,
                tenant_id=tenant_id,
                role=r,
                source_type="INTERNAL",
                is_active=True,
            ))
            all_roles.append(r)
        db.commit()

    # v1.5.5 — 创建后立即生成一次性 OTP（purpose=login）+ 返回手机号 + OTP
    # 让前端直接弹「二维码 + OTP」邀请 modal，无需二次请求
    response = _user_to_response(new_user, body.role)
    if login_method == "otp":
        from .auth_extras import _create_otp
        try:
            initial_code = _create_otp(db, body.phone, "login")
            dev_return = os.getenv("OTP_DEV_RETURN", "true").lower() == "true"
            response.initial_otp = initial_code if dev_return else None
            response.phone_full = body.phone if dev_return else None
        except HTTPException:
            # rate limit 等异常不阻断创建
            pass
    response.email = new_user.email
    response.last_login_at = new_user.last_login_at
    response.login_method = new_user.login_method
    response.all_roles = all_roles
    return response


@router.patch("/users/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: int,
    body: UserUpdateByAdminRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    actor: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    """v1.5.5 — admin 编辑员工。"""
    from app.services.audit import log_audit

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    target = db.get(UserAccount, user_id)
    if target is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    memberships = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalars().all()
    if not memberships:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_IN_TENANT", "message": "用户不属本租户"},
        )

    # 自锁防御：不能改自己的 role / is_active / roles
    is_self = target.id == actor.id
    if is_self and (
        body.role is not None or body.is_active is not None or body.roles is not None
    ):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_SELF_LOCK", "message": "不能修改自己的角色或启用状态"},
        )

    changes: dict[str, object] = {}
    if body.name is not None and body.name != target.name:
        changes["name"] = {"from": target.name, "to": body.name}
        target.name = body.name
    if body.email is not None and body.email != target.email:
        existing = db.execute(
            select(UserAccount).where(UserAccount.email == body.email)
        ).scalar_one_or_none()
        if existing and existing.id != target.id:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={"code": "ERR_EMAIL_TAKEN", "message": "邮箱已被占用"},
            )
        changes["email"] = {"from": target.email, "to": body.email}
        target.email = body.email
    if body.is_active is not None and body.is_active != target.is_active:
        changes["is_active"] = {"from": target.is_active, "to": body.is_active}
        target.is_active = body.is_active

    # v1.5.6 — roles 列表 reconcile：完整覆盖该用户在本租户的 active membership
    if body.roles is not None:
        new_roles = set(body.roles)
        if not new_roles:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_NO_ROLE", "message": "至少需要保留 1 个角色"},
            )
        existing_by_role = {m.role: m for m in memberships}
        old_role_set = set(existing_by_role.keys())
        # 失活需要移除的
        to_remove = old_role_set - new_roles
        for r in to_remove:
            existing_by_role[r].is_active = False
        # 新增缺失的
        to_add = new_roles - old_role_set
        for r in to_add:
            db.add(UserTenantMembership(
                user_id=target.id,
                tenant_id=tenant_id,
                role=r,
                source_type="INTERNAL",
                is_active=True,
            ))
        if to_remove or to_add:
            changes["roles"] = {
                "from": sorted(old_role_set),
                "to": sorted(new_roles),
            }
    elif body.role is not None:
        # 旧路径：只改第一个 membership 的 role（backward compat）
        first_m = memberships[0]
        if body.role != first_m.role:
            changes["role"] = {"from": first_m.role, "to": body.role}
            first_m.role = body.role

    if changes:
        log_audit(
            db,
            actor_user_id=actor.id,
            actor_role=payload.get("role"),
            tenant_id=tenant_id,
            action="admin.user_updated",
            target_type="user",
            target_id=target.id,
            payload=changes,
        )
    db.commit()
    db.refresh(target)
    # 重新拉取所有 active membership
    final_roles = list(db.execute(
        select(UserTenantMembership.role).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalars().all())
    primary = final_roles[0] if final_roles else memberships[0].role
    response = _user_to_response(target, primary)
    response.email = target.email
    response.last_login_at = target.last_login_at
    response.login_method = target.login_method
    response.all_roles = final_roles
    return response


@router.post("/users/{user_id}/issue-otp", response_model=UserOtpIssueOut)
async def issue_user_otp(
    user_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    actor: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserOtpIssueOut:
    """v1.5.5 — 给员工重新生成一次性首登 OTP。"""
    from app.services.audit import log_audit

    from .auth_extras import _create_otp

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    target = db.get(UserAccount, user_id)
    membership = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if target is None or membership is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )

    phone = decrypt_phone(target.phone_enc)
    code = _create_otp(db, phone, "login")
    dev_return = os.getenv("OTP_DEV_RETURN", "true").lower() == "true"

    log_audit(
        db,
        actor_user_id=actor.id,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="admin.user_otp_issued",
        target_type="user",
        target_id=target.id,
        payload=None,
    )
    db.commit()
    return UserOtpIssueOut(
        phone_masked=mask_phone(target.phone_enc),
        phone_full=phone if dev_return else None,
        otp=code if dev_return else None,
    )


@router.get("/devices", response_model=list[AdminDeviceItem])
async def list_devices(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    user_id: int | None = Query(None),
) -> list[AdminDeviceItem]:
    """Sprint 12 — admin troubleshooting: see whether a user's device is push-registered.

    The raw push_reg_id is never exposed; callers see only push_reg_id_set.
    Scoped to the caller's tenant.
    """
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    stmt = select(DeviceProfile).where(DeviceProfile.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(DeviceProfile.user_id == user_id)
    stmt = stmt.order_by(DeviceProfile.id.desc())

    devices = db.execute(stmt).scalars().all()
    return [
        AdminDeviceItem(
            device_id=d.device_id,
            user_id=d.user_id,
            brand=d.brand,
            model=d.model,
            os_version=d.os_version,
            push_reg_id_set=bool(d.push_reg_id),
            push_provider=d.push_provider,
            is_healthy=d.is_healthy,
            last_check_at=d.last_check_at,
            created_at=d.created_at,
        )
        for d in devices
    ]


# ── v1.5.6 收尾：内部催收员提成统计（应发员工提成）─────────────────────


class AgentCommissionItem(BaseModel):
    user_id: int
    name: str
    phone_masked: str
    year_month: str
    commission_rate: float
    base_amount: Decimal
    paid_case_count: int
    commission: Decimal


class AgentCommissionList(BaseModel):
    year_month: str
    total_base: Decimal
    total_commission: Decimal
    items: list[AgentCommissionItem]


class AgentCommissionLineItem(BaseModel):
    case_id: int
    owner_name: str
    paid_amount: Decimal
    paid_at: datetime


class AgentCommissionDetail(BaseModel):
    user_id: int
    name: str
    year_month: str
    commission_rate: float
    base_amount: Decimal
    commission: Decimal
    items: list[AgentCommissionLineItem]


# 与 provider_admin.DEFAULT_COMMISSION_RATE 一致；v1.6 接租户级配置
INTERNAL_AGENT_COMMISSION_RATE = 0.05


def _month_window(year_month: str) -> tuple[datetime, datetime]:
    from datetime import UTC

    year, month = (int(p) for p in year_month.split("-"))
    period_start = datetime(year, month, 1, tzinfo=UTC)
    period_end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    return period_start, period_end


@router.get("/agent-commissions", response_model=AgentCommissionList)
async def list_agent_commissions(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> AgentCommissionList:
    """v1.5.6 — 物业内部催收员当月提成（应发员工工资视图）。"""
    from decimal import Decimal as D

    from app.core.crypto import mask_phone
    from app.models.case import CollectionCase

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    period_start, period_end = _month_window(year_month)

    # 拉本租户所有 active agent_internal
    agents = db.execute(
        select(UserAccount, UserTenantMembership)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role == "agent_internal",
            UserTenantMembership.is_active.is_(True),
            UserAccount.is_active.is_(True),
        )
        .order_by(UserAccount.id)
    ).all()

    items: list[AgentCommissionItem] = []
    for u, _m in agents:
        rows = db.execute(
            select(CollectionCase.amount_owed).where(
                CollectionCase.assigned_to == u.id,
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= period_start,
                CollectionCase.updated_at < period_end,
            )
        ).all()
        base = sum((D(str(r[0] or 0)) for r in rows), D("0"))
        commission = (base * D(str(INTERNAL_AGENT_COMMISSION_RATE))).quantize(D("0.01"))
        items.append(AgentCommissionItem(
            user_id=u.id,
            name=u.name,
            phone_masked=mask_phone(u.phone_enc),
            year_month=year_month,
            commission_rate=INTERNAL_AGENT_COMMISSION_RATE,
            base_amount=base,
            paid_case_count=len(rows),
            commission=commission,
        ))
    total_base = sum((it.base_amount for it in items), D("0"))
    total_commission = sum((it.commission for it in items), D("0"))
    return AgentCommissionList(
        year_month=year_month,
        total_base=total_base,
        total_commission=total_commission,
        items=items,
    )


@router.get("/agent-commissions/{user_id}", response_model=AgentCommissionDetail)
async def get_agent_commission_detail(
    user_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> AgentCommissionDetail:
    """v1.5.6 — 单个内部催收员当月提成明细（每个 paid 案件一行）。"""
    from decimal import Decimal as D

    from app.models.case import CollectionCase, OwnerProfile

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    target = db.get(UserAccount, user_id)
    if target is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )

    period_start, period_end = _month_window(year_month)
    rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.assigned_to == user_id,
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "paid",
            CollectionCase.updated_at >= period_start,
            CollectionCase.updated_at < period_end,
        ).order_by(CollectionCase.updated_at.desc())
    ).all()

    items = [
        AgentCommissionLineItem(
            case_id=c.id,
            owner_name=o.name,
            paid_amount=D(str(c.amount_owed or 0)),
            paid_at=c.updated_at,
        )
        for c, o in rows
    ]
    base = sum((it.paid_amount for it in items), D("0"))
    commission = (base * D(str(INTERNAL_AGENT_COMMISSION_RATE))).quantize(D("0.01"))
    return AgentCommissionDetail(
        user_id=target.id,
        name=target.name,
        year_month=year_month,
        commission_rate=INTERNAL_AGENT_COMMISSION_RATE,
        base_amount=base,
        commission=commission,
        items=items,
    )


# ── v1.5.7 — 物业 admin 成本汇总（结算管理 Tab 3）──────────────────────


class CostSummaryOut(BaseModel):
    year_month: str
    provider_payable_total: Decimal      # 应付服务商
    agent_commission_total: Decimal      # 应发员工提成
    total_cost: Decimal                  # 合计
    provider_count: int                  # 涉及服务商数
    agent_count: int                     # 涉及内勤数
    paid_case_count: int                 # 当月已结清案件数（共计）


@router.get("/cost-summary", response_model=CostSummaryOut)
async def admin_cost_summary(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    year_month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
) -> CostSummaryOut:
    """v1.5.7 — 一屏盘点本月外部应付 + 内部应发 + 案件总数。"""
    from decimal import Decimal as D

    from app.models.case import CollectionCase, Project
    from app.models.settlement import SettlementStatement
    from app.models.tenant import ProviderTenantContract

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    period_start, period_end = _month_window(year_month)

    # 应付服务商：本租户合同对应的 settlement statement，期间归属看 period_start
    settle_rows = db.execute(
        select(SettlementStatement, ProviderTenantContract.provider_id)
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            ProviderTenantContract.tenant_id == tenant_id,
            SettlementStatement.period_start >= period_start,
            SettlementStatement.period_start < period_end,
        )
    ).all()
    provider_total = sum(
        (D(str(s.total_amount or 0)) for s, _pid in settle_rows), D("0"),
    )
    provider_ids = {pid for _s, pid in settle_rows if pid}

    # 应发员工提成：复用 list_agent_commissions 算法
    agents = db.execute(
        select(UserAccount.id).join(
            UserTenantMembership, UserTenantMembership.user_id == UserAccount.id
        ).where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role == "agent_internal",
            UserTenantMembership.is_active.is_(True),
            UserAccount.is_active.is_(True),
        )
    ).scalars().all()
    agent_total = D("0")
    agent_count_with_payout = 0
    for uid in agents:
        rows = db.execute(
            select(CollectionCase.amount_owed).where(
                CollectionCase.assigned_to == uid,
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= period_start,
                CollectionCase.updated_at < period_end,
            )
        ).all()
        base = sum((D(str(r[0] or 0)) for r in rows), D("0"))
        if base > 0:
            agent_count_with_payout += 1
        agent_total += (base * D(str(INTERNAL_AGENT_COMMISSION_RATE))).quantize(
            D("0.01")
        )

    # 当月本租户结清案件总数
    paid_case_total: int = db.execute(
        select(func.count()).select_from(
            select(CollectionCase.id).join(
                Project, Project.id == CollectionCase.project_id, isouter=True
            ).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= period_start,
                CollectionCase.updated_at < period_end,
            ).subquery()
        )
    ).scalar_one()

    return CostSummaryOut(
        year_month=year_month,
        provider_payable_total=provider_total,
        agent_commission_total=agent_total,
        total_cost=provider_total + agent_total,
        provider_count=len(provider_ids),
        agent_count=agent_count_with_payout,
        paid_case_count=paid_case_total,
    )


# ── v1.5.7 — 物业 admin 审计日志列表 ──────────────────────────────


from app.schemas.audit import AuditLogOut


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
async def admin_audit_logs(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    action: str | None = Query(None, max_length=100),
    actor_user_id: int | None = Query(None, ge=1),
    target_type: str | None = Query(None, max_length=50),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogOut]:
    """v1.5.7 — 物业 admin 看本租户审计事件（按时间倒序）。"""
    from app.models.audit import AuditLog

    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at <= until)

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
    )
    return PaginatedResponse(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )
