from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.script import TenantSuggestionConfig
from app.schemas.script import SuggestionConfigOut, SuggestionConfigUpdate

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")
_DEFAULTS = SuggestionConfigOut(sensitivity=3, max_per_push=3)


@router.get("/suggestion-config", response_model=SuggestionConfigOut)
def get_config(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SuggestionConfigOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    cfg = db.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if cfg is None:
        return _DEFAULTS
    return SuggestionConfigOut(sensitivity=cfg.sensitivity, max_per_push=cfg.max_per_push)


@router.put("/suggestion-config", response_model=SuggestionConfigOut)
def put_config(
    body: SuggestionConfigUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SuggestionConfigOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    cfg = db.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if cfg is None:
        cfg = TenantSuggestionConfig(tenant_id=tenant_id)
        db.add(cfg)

    cfg.sensitivity = body.sensitivity
    cfg.max_per_push = body.max_per_push
    cfg.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(cfg)
    return SuggestionConfigOut(sensitivity=cfg.sensitivity, max_per_push=cfg.max_per_push)
