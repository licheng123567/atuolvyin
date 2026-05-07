"""Sprint 16.4 — Bilateral termination handshake (D2).

物业 / 服务商任一方发起解约 → 对方在 7 天内确认 → status=terminated；
任一方 7 天不确认 → daily worker 自动 terminated（详见
`app/workers/scheduled/terminate_timeout.py`）。

端点：
    物业侧：
      POST /api/v1/admin/providers/{provider_id}/terminate-request
      POST /api/v1/admin/providers/{provider_id}/terminate-confirm
    服务商侧：
      POST /api/v1/provider/contracts/{contract_id}/terminate-request
      POST /api/v1/provider/contracts/{contract_id}/terminate-confirm
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    UserTenantMembership,
)
from app.schemas.admin_provider import (
    TerminateRequestIn,
    TerminationStatusOut,
)
from app.services.audit import log_audit

REQUEST_PARTY_PROPERTY = 1
REQUEST_PARTY_PROVIDER = 2
CONFIRM_TIMEOUT_DAYS = 7

ADMIN_ROLES = ("admin", "platform_superadmin")
PROVIDER_ADMIN_ROLES = ("provider_admin",)

admin_router = APIRouter()
provider_router = APIRouter()


def _to_status_out(c: ProviderTenantContract) -> TerminationStatusOut:
    days_remaining: int | None = None
    if (
        c.termination_requested_at is not None
        and c.termination_confirmed_at is None
        and c.status != "terminated"
    ):
        deadline = c.termination_requested_at + timedelta(days=CONFIRM_TIMEOUT_DAYS)
        delta = deadline - datetime.now(UTC)
        days_remaining = max(0, delta.days)
    return TerminationStatusOut(
        contract_id=c.id,
        status=c.status,
        termination_requested_by=c.termination_requested_by,
        termination_requested_at=c.termination_requested_at,
        termination_reason=c.termination_reason,
        termination_confirmed_at=c.termination_confirmed_at,
        terminated_at=c.terminated_at,
        timeout_days_remaining=days_remaining,
    )


def _load_active_contract_admin(
    db: Session, tenant_id: int, provider_id: int
) -> ProviderTenantContract:
    c = db.execute(
        select(ProviderTenantContract)
        .where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.provider_id == provider_id,
        )
        .order_by(ProviderTenantContract.signed_at.desc())
    ).scalars().first()
    if c is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "未与该服务商签约"},
        )
    return c


def _load_contract_provider_side(
    db: Session, user_id: int, contract_id: int
) -> ProviderTenantContract:
    m = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.role == "provider_admin",
        )
    ).scalars().first()
    if m is None or m.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定服务商"},
        )
    c = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.id == contract_id,
            ProviderTenantContract.provider_id == int(m.provider_id),
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "合同不存在"},
        )
    return c


def _audit(
    db: Session,
    payload: dict,
    tenant_id: int,
    contract: ProviderTenantContract,
    action: str,
) -> None:
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action=action,
        target_type="provider_tenant_contract",
        target_id=contract.id,
        payload={
            "provider_id": contract.provider_id,
            "tenant_id": contract.tenant_id,
            "status": contract.status,
        },
    )


def _do_terminate_request(
    db: Session,
    contract: ProviderTenantContract,
    requested_by: int,
    body: TerminateRequestIn,
    payload: dict,
    tenant_id: int,
) -> ProviderTenantContract:
    if contract.status == "terminated":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_TERMINATED", "message": "合同已终止"},
        )
    if contract.termination_requested_at is not None and contract.termination_confirmed_at is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_REQUEST_PENDING",
                "message": "已有未确认的解约请求，请等待对方处理",
            },
        )
    contract.termination_requested_by = requested_by
    contract.termination_requested_at = datetime.now(UTC)
    contract.termination_reason = body.reason
    contract.termination_confirmed_at = None
    _audit(
        db,
        payload,
        tenant_id,
        contract,
        "provider.contract.terminate_requested",
    )
    db.commit()
    db.refresh(contract)
    return contract


def _do_terminate_confirm(
    db: Session,
    contract: ProviderTenantContract,
    confirmer_party: int,
    payload: dict,
    tenant_id: int,
) -> ProviderTenantContract:
    if contract.status == "terminated":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_TERMINATED", "message": "合同已终止"},
        )
    if contract.termination_requested_at is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_NO_REQUEST",
                "message": "尚未有解约请求，无需确认",
            },
        )
    if contract.termination_requested_by == confirmer_party:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_SELF_CONFIRM",
                "message": "请由对方确认解约",
            },
        )
    now = datetime.now(UTC)
    contract.termination_confirmed_at = now
    contract.terminated_at = now
    contract.status = "terminated"
    _audit(
        db, payload, tenant_id, contract, "provider.contract.terminated"
    )
    db.commit()
    db.refresh(contract)
    return contract


# ── Property admin side ─────────────────────────────────────────────


def _admin_tenant(payload: dict) -> int:
    tid = payload.get("tenant_id")
    if not tid:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前账号未绑定租户"},
        )
    return int(tid)


@admin_router.post(
    "/providers/{provider_id}/terminate-request",
    response_model=TerminationStatusOut,
)
async def admin_request_terminate(
    provider_id: int,
    body: TerminateRequestIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    tenant_id = _admin_tenant(payload)
    c = _load_active_contract_admin(db, tenant_id, provider_id)
    c = _do_terminate_request(
        db, c, REQUEST_PARTY_PROPERTY, body, payload, tenant_id
    )
    return _to_status_out(c)


@admin_router.post(
    "/providers/{provider_id}/terminate-confirm",
    response_model=TerminationStatusOut,
)
async def admin_confirm_terminate(
    provider_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    tenant_id = _admin_tenant(payload)
    c = _load_active_contract_admin(db, tenant_id, provider_id)
    c = _do_terminate_confirm(
        db, c, REQUEST_PARTY_PROPERTY, payload, tenant_id
    )
    return _to_status_out(c)


@admin_router.get(
    "/providers/{provider_id}/termination-status",
    response_model=TerminationStatusOut,
)
async def admin_get_termination_status(
    provider_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    tenant_id = _admin_tenant(payload)
    c = _load_active_contract_admin(db, tenant_id, provider_id)
    return _to_status_out(c)


# ── Provider admin side ─────────────────────────────────────────────


@provider_router.post(
    "/contracts/{contract_id}/terminate-request",
    response_model=TerminationStatusOut,
)
async def provider_request_terminate(
    contract_id: int,
    body: TerminateRequestIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    user_id = int(payload.get("user_id") or 0)
    c = _load_contract_provider_side(db, user_id, contract_id)
    c = _do_terminate_request(
        db, c, REQUEST_PARTY_PROVIDER, body, payload, c.tenant_id
    )
    return _to_status_out(c)


@provider_router.post(
    "/contracts/{contract_id}/terminate-confirm",
    response_model=TerminationStatusOut,
)
async def provider_confirm_terminate(
    contract_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    user_id = int(payload.get("user_id") or 0)
    c = _load_contract_provider_side(db, user_id, contract_id)
    c = _do_terminate_confirm(
        db, c, REQUEST_PARTY_PROVIDER, payload, c.tenant_id
    )
    return _to_status_out(c)


@provider_router.get(
    "/contracts/{contract_id}/termination-status",
    response_model=TerminationStatusOut,
)
async def provider_get_termination_status(
    contract_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TerminationStatusOut:
    user_id = int(payload.get("user_id") or 0)
    c = _load_contract_provider_side(db, user_id, contract_id)
    return _to_status_out(c)


# Surface a list of partner contracts for the provider admin (used by the
# dashboard top banner to detect any pending termination request)
@provider_router.get(
    "/contracts",
    response_model=list[TerminationStatusOut],
)
async def provider_list_contracts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[TerminationStatusOut]:
    user_id = int(payload.get("user_id") or 0)
    m = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.role == "provider_admin",
        )
    ).scalars().first()
    if m is None or m.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定服务商"},
        )
    rows = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.provider_id == int(m.provider_id)
        )
    ).scalars().all()
    return [_to_status_out(c) for c in rows]


# Reference _ServiceProvider to keep import non-empty when used in tests
__all__ = [
    "admin_router",
    "provider_router",
    "REQUEST_PARTY_PROPERTY",
    "REQUEST_PARTY_PROVIDER",
    "CONFIRM_TIMEOUT_DAYS",
]
_ = ServiceProvider  # keep import side-effect
