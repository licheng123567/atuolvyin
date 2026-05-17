"""Sprint 8 — 物业管理员视角的「服务商合作管理」(PRD §3.9, L2044).

A property admin (`admin` role) manages contracts between their own tenant
and platform-approved Service Providers. They can:
  * list signed providers (with member counts)
  * see which approved providers are still available to invite
  * invite a new provider (creates a ProviderTenantContract)
  * inspect provider members assigned to this tenant
  * adjust contract (expires_at / service_types / status)
  * adjust member quota / expire_at / access_hours / is_active

All endpoints scope by the requesting admin's tenant_id (from JWT).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.crypto import mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.schemas.admin_provider import (
    AdminAvailableProviderItem,
    AdminProviderContractOut,
    AdminProviderContractPatchIn,
    AdminProviderInviteIn,
    AdminProviderListItem,
    AdminProviderMemberOut,
    AdminProviderMemberPatchIn,
)
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")


def _tenant_id(payload: dict) -> int:
    tid = payload.get("tenant_id")
    if not tid:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前账号未绑定租户"},
        )
    return int(tid)


# ── List signed providers (with member_count) ───────────────────────


@router.get("/providers", response_model=list[AdminProviderListItem])
async def list_signed_providers(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern=r"^(active|paused|terminated)$"),
) -> list[AdminProviderListItem]:
    tenant_id = _tenant_id(payload)

    contract_stmt = (
        select(ProviderTenantContract, ServiceProvider)
        .join(ServiceProvider, ServiceProvider.id == ProviderTenantContract.provider_id)
        .where(ProviderTenantContract.tenant_id == tenant_id)
    )
    if q:
        contract_stmt = contract_stmt.where(ServiceProvider.name.ilike(f"%{q}%"))
    if status:
        contract_stmt = contract_stmt.where(ProviderTenantContract.status == status)

    rows = db.execute(contract_stmt.order_by(ProviderTenantContract.signed_at.desc())).all()

    if not rows:
        return []

    provider_ids = [p.id for _, p in rows]
    counts: dict[int, int] = dict(
        db.execute(
            select(
                UserTenantMembership.provider_id,
                func.count(UserTenantMembership.id),
            )
            .where(
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.provider_id.in_(provider_ids),
            )
            .group_by(UserTenantMembership.provider_id)
        ).all()
    )

    return [
        AdminProviderListItem(
            provider_id=p.id,
            provider_name=p.name,
            provider_type=p.provider_type,
            contract_id=c.id,
            signed_at=c.signed_at,
            expires_at=c.expires_at,
            service_types=list(c.service_types or []),
            status=c.status,
            member_count=int(counts.get(p.id, 0)),
        )
        for c, p in rows
    ]


# ── Available (approved, no active contract) providers ──────────────


@router.get("/providers/available", response_model=list[AdminAvailableProviderItem])
async def list_available_providers(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
) -> list[AdminAvailableProviderItem]:
    tenant_id = _tenant_id(payload)

    signed_provider_ids_subq = (
        select(ProviderTenantContract.provider_id)
        .where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.status == "active",
        )
        .scalar_subquery()
    )

    stmt = select(ServiceProvider).where(
        ServiceProvider.audit_status == "approved",
        ServiceProvider.is_active.is_(True),
        ServiceProvider.id.notin_(signed_provider_ids_subq),
    )
    if q:
        stmt = stmt.where(ServiceProvider.name.ilike(f"%{q}%"))

    rows = db.execute(stmt.order_by(ServiceProvider.name.asc())).scalars().all()
    return [AdminAvailableProviderItem.model_validate(p) for p in rows]


# ── Invite (create contract) ────────────────────────────────────────


@router.post(
    "/providers/invite",
    response_model=AdminProviderContractOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def invite_provider(
    body: AdminProviderInviteIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminProviderContractOut:
    tenant_id = _tenant_id(payload)

    provider = db.get(ServiceProvider, body.provider_id)
    if provider is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "服务商不存在"},
        )
    if provider.audit_status != "approved" or not provider.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_PROVIDER_NOT_AVAILABLE",
                "message": "该服务商未通过审核或已停用",
            },
        )

    existing = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.provider_id == body.provider_id,
            ProviderTenantContract.status == "active",
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_DUPLICATE_CONTRACT",
                "message": "已与该服务商存在有效合作",
            },
        )

    contract = ProviderTenantContract(
        tenant_id=tenant_id,
        provider_id=body.provider_id,
        signed_at=datetime.now(UTC),
        expires_at=body.expires_at,
        service_types=body.service_types,
        status="active",
    )
    db.add(contract)
    db.flush()
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="provider.invite",
        target_type="provider_tenant_contract",
        target_id=contract.id,
        payload={
            "provider_id": body.provider_id,
            "service_types": body.service_types,
        },
    )
    db.commit()
    db.refresh(contract)

    return AdminProviderContractOut(
        contract_id=contract.id,
        provider_id=provider.id,
        provider_name=provider.name,
        signed_at=contract.signed_at,
        expires_at=contract.expires_at,
        service_types=list(contract.service_types or []),
        status=contract.status,
    )


# ── Update contract ─────────────────────────────────────────────────


@router.patch(
    "/providers/{provider_id}/contract",
    response_model=AdminProviderContractOut,
)
async def patch_contract(
    provider_id: int,
    body: AdminProviderContractPatchIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminProviderContractOut:
    tenant_id = _tenant_id(payload)
    row = db.execute(
        select(ProviderTenantContract, ServiceProvider)
        .join(ServiceProvider, ServiceProvider.id == ProviderTenantContract.provider_id)
        .where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.provider_id == provider_id,
        )
        .order_by(ProviderTenantContract.signed_at.desc())
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "未与该服务商签约"},
        )
    contract, provider = row

    data = body.model_dump(exclude_unset=True)
    # v1.4 S16.4 — 直接 PATCH 到 terminated 已被 schema 屏蔽（Literal 不含 terminated），
    # 但作为后端二次防线，仍校验，防止绕过 schema 调用。
    if data.get("status") == "terminated":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_USE_TERMINATE_REQUEST",
                "message": "请走 /providers/{id}/terminate-request 双向握手流程",
            },
        )
    for field, value in data.items():
        setattr(contract, field, value)

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="provider.contract.update",
        target_type="provider_tenant_contract",
        target_id=contract.id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(contract)

    return AdminProviderContractOut(
        contract_id=contract.id,
        provider_id=provider.id,
        provider_name=provider.name,
        signed_at=contract.signed_at,
        expires_at=contract.expires_at,
        service_types=list(contract.service_types or []),
        status=contract.status,
    )


# ── Members (provider staff assigned to this tenant) ────────────────


@router.get(
    "/providers/{provider_id}/members",
    response_model=list[AdminProviderMemberOut],
)
async def list_provider_members(
    provider_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[AdminProviderMemberOut]:
    tenant_id = _tenant_id(payload)

    contract = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.provider_id == provider_id,
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "未与该服务商签约"},
        )

    rows = db.execute(
        select(UserAccount, UserTenantMembership)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.provider_id == provider_id,
        )
        .order_by(UserAccount.id.asc())
    ).all()

    return [
        AdminProviderMemberOut(
            user_id=u.id,
            name=u.name,
            phone_masked=mask_phone(u.phone_enc),
            role=m.role,
            quota=m.quota,
            expire_at=m.expire_at,
            access_hours=m.access_hours,
            is_active=m.is_active and u.is_active,
        )
        for u, m in rows
    ]


@router.patch(
    "/providers/{provider_id}/members/{user_id}",
    response_model=AdminProviderMemberOut,
)
async def patch_provider_member(
    provider_id: int,
    user_id: int,
    body: AdminProviderMemberPatchIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminProviderMemberOut:
    tenant_id = _tenant_id(payload)

    row = db.execute(
        select(UserAccount, UserTenantMembership)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserAccount.id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.provider_id == provider_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "成员不存在或不属于该服务商"},
        )
    user, membership = row

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(membership, field, value)

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="provider.member.update",
        target_type="user_tenant_membership",
        target_id=membership.id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(membership)
    db.refresh(user)

    return AdminProviderMemberOut(
        user_id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=membership.role,
        quota=membership.quota,
        expire_at=membership.expire_at,
        access_hours=membership.access_hours,
        is_active=membership.is_active and user.is_active,
    )
