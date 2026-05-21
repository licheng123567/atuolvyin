"""Sprint 8.5 — Admin tenant settings (PRD §3.14 / L2049).

Covers the gaps in 系统配置 not handled elsewhere:
  - 录音模式（live/post/auto）
  - L3 挂断开关
  - 联系频次上限
  - 数据保留期

Existing settings handled by their own routers:
  - AI 推送灵敏度 → admin_suggestion_config
  - 风控自定义词 → admin_risk_keywords
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.settings import TenantSettings
from app.schemas.settings import TenantSettingsOut, TenantSettingsUpdate
from app.services.audit import log_audit

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")

DEFAULTS = TenantSettingsOut(
    recording_mode="auto",
    l3_hangup_enabled=False,
    contact_freq_max=3,
    retention_days=365,
    discount_auto_approve_threshold_pct=10,
    discount_supervisor_max_pct=30,
    discount_disabled=False,
    late_fee_waive_auto_approve_threshold_pct=50,
    late_fee_waive_supervisor_max_pct=100,
    late_fee_waive_disabled=False,
    notify_quota_warning=True,
    notify_script_disabled=True,
    notify_work_order_completed=True,
    notify_case_escalated=True,
    notify_promise_expiring=True,
    notify_channels=["system"],
    auto_release_stale_days=0,
)


def _to_out(s: TenantSettings) -> TenantSettingsOut:
    return TenantSettingsOut(
        recording_mode=s.recording_mode,  # type: ignore[arg-type]
        l3_hangup_enabled=s.l3_hangup_enabled,
        contact_freq_max=s.contact_freq_max,
        retention_days=s.retention_days,
        discount_auto_approve_threshold_pct=s.discount_auto_approve_threshold_pct,
        discount_supervisor_max_pct=s.discount_supervisor_max_pct,
        discount_disabled=s.discount_disabled,
        late_fee_waive_auto_approve_threshold_pct=getattr(
            s, "late_fee_waive_auto_approve_threshold_pct", 50
        )
        or 50,
        late_fee_waive_supervisor_max_pct=getattr(s, "late_fee_waive_supervisor_max_pct", 100)
        or 100,
        late_fee_waive_disabled=getattr(s, "late_fee_waive_disabled", False) or False,
        notify_quota_warning=s.notify_quota_warning,
        notify_script_disabled=s.notify_script_disabled,
        notify_work_order_completed=s.notify_work_order_completed,
        notify_case_escalated=s.notify_case_escalated,
        notify_promise_expiring=s.notify_promise_expiring,
        notify_channels=list(s.notify_channels) if s.notify_channels else ["system"],  # type: ignore[arg-type]
        # v0.9.0 — getattr 兜底:旧迁移未跑前 attribute 不存在
        auto_release_stale_days=getattr(s, "auto_release_stale_days", 0) or 0,
    )


@router.get("/settings", response_model=TenantSettingsOut)
def get_settings(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantSettingsOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    s = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return _to_out(s) if s else DEFAULTS


@router.patch("/settings", response_model=TenantSettingsOut)
def patch_settings(
    body: TenantSettingsUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantSettingsOut:
    tenant_id = int(payload.get("tenant_id") or 0)

    s = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if s is None:
        s = TenantSettings(tenant_id=tenant_id)
        db.add(s)

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(s, field, value)

    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="settings.update",
        target_type="tenant_settings",
        target_id=tenant_id,
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(s)
    return _to_out(s)
