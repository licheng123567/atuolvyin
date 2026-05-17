"""Sprint 16.3 — admin provider recommendation (D1).

物业 admin 可以推荐服务商入驻平台（仍由 ops 审批）：

    POST /api/v1/admin/providers/recommend

写入 ServiceProvider(audit_status='pending', recommended_by_tenant_id=<本租户>)。
ops 端可以在 GET /api/v1/ops/providers?audit_status=pending 看到推荐人。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.tenant import ServiceProvider
from app.schemas.provider import ProviderOut, ProviderRecommendIn
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")


def _to_out(p: ServiceProvider) -> ProviderOut:
    return ProviderOut(
        id=p.id,
        name=p.name,
        provider_type=p.provider_type,
        admin_phone_masked=mask_phone(p.admin_phone_enc),
        contact_email=p.contact_email,
        description=p.description,
        monthly_minute_quota=p.monthly_minute_quota,
        is_active=p.is_active,
        audit_status=p.audit_status,
        audit_reason=p.audit_reason,
        audit_at=p.audit_at,
        created_at=p.created_at,
        recommended_by_tenant_id=p.recommended_by_tenant_id,
        recommended_by_tenant_name=None,
    )


@router.post(
    "/providers/recommend",
    response_model=ProviderOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def recommend_provider(
    body: ProviderRecommendIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderOut:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前账号未绑定租户"},
        )
    tenant_id = int(tenant_id)

    p = ServiceProvider(
        name=body.name,
        provider_type=body.provider_type,
        admin_phone_enc=encrypt_phone(body.admin_phone),
        contact_email=body.contact_email,
        description=body.description,
        is_active=True,
        audit_status="pending",
        recommended_by_tenant_id=tenant_id,
    )
    db.add(p)
    db.flush()
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="provider.recommended",
        target_type="service_provider",
        target_id=p.id,
        payload={"name": p.name, "provider_type": p.provider_type},
    )
    db.commit()
    db.refresh(p)
    return _to_out(p)
