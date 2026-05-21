"""v0.9.0 — 服务商 admin 设置页后端。

当前仅含 N 天未联系自动释放公海配置(auto_release_stale_days),
与物业 admin 的 /api/v1/admin/settings 对称。

服务商 admin 设置作用于:
  - 本服务商接的案件(scope=provider_id)
  - 本服务商内催收员持有
  - N 天 last_contact_at 阈值
  - 释放进服务商内部公海(case.pool_type='provider_pool:{provider_id}')

定时任务读 ProviderSettings(同 TenantSettings),逐 provider 扫描。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_provider_roles
from app.models.settings import ProviderSettings
from app.models.tenant import UserTenantMembership
from app.schemas.settings import ProviderSettingsOut, ProviderSettingsUpdate
from app.services.audit import log_audit

router = APIRouter()

# 仅服务商 admin 可读写自家配置;PM 暂不开(后续需要再放宽)
PROVIDER_ADMIN_ROLES = ("admin",)


def _resolve_provider_id(payload: dict, db: Session) -> int:
    """从 token 关联 provider_id;若无则 404 ERR_NO_PROVIDER。"""
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token payload"},
        )
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
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定任何服务商"},
        )
    return int(membership.provider_id)


@router.get("/settings", response_model=ProviderSettingsOut)
def get_provider_settings(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderSettingsOut:
    provider_id = _resolve_provider_id(payload, db)
    s = db.execute(
        select(ProviderSettings).where(ProviderSettings.provider_id == provider_id)
    ).scalar_one_or_none()
    if s is None:
        return ProviderSettingsOut()  # 默认值
    return _to_out(s)


@router.patch("/settings", response_model=ProviderSettingsOut)
def patch_provider_settings(
    body: ProviderSettingsUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderSettingsOut:
    provider_id = _resolve_provider_id(payload, db)

    s = db.execute(
        select(ProviderSettings).where(ProviderSettings.provider_id == provider_id)
    ).scalar_one_or_none()
    if s is None:
        s = ProviderSettings(provider_id=provider_id)
        db.add(s)

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(s, field, value)

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=int(payload.get("tenant_id") or 0) or None,
        action="provider_settings.update",
        target_type="provider_settings",
        target_id=provider_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(s)
    return _to_out(s)


def _to_out(s: ProviderSettings) -> ProviderSettingsOut:
    """v1.0.0 — getattr 兜底:旧迁移未跑前 attribute 不存在,回落默认值。"""
    return ProviderSettingsOut(
        auto_release_stale_days=s.auto_release_stale_days or 0,
        recording_mode=getattr(s, "recording_mode", "auto") or "auto",
        contact_freq_max=getattr(s, "contact_freq_max", 3) or 3,
        notify_quota_warning=getattr(s, "notify_quota_warning", True),
        notify_script_disabled=getattr(s, "notify_script_disabled", True),
        notify_work_order_completed=getattr(s, "notify_work_order_completed", True),
        notify_case_escalated=getattr(s, "notify_case_escalated", True),
        notify_promise_expiring=getattr(s, "notify_promise_expiring", True),
        notify_channels=list(getattr(s, "notify_channels", ["system"]) or ["system"]),
    )
