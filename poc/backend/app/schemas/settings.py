"""Sprint 8.5 / 12.3 — Tenant settings schemas (PRD §3.14 / §L412)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NotifyChannel = Literal["system", "sms", "wechat", "dingtalk"]


class TenantSettingsOut(BaseModel):
    recording_mode: Literal["live", "post", "auto"]
    l3_hangup_enabled: bool
    contact_freq_max: int
    retention_days: int
    # Sprint 12.3 — 通知规则
    notify_quota_warning: bool = True
    notify_script_disabled: bool = True
    notify_work_order_completed: bool = True
    notify_case_escalated: bool = True
    notify_promise_expiring: bool = True
    notify_channels: list[NotifyChannel] = ["system"]


class TenantSettingsUpdate(BaseModel):
    recording_mode: Literal["live", "post", "auto"] | None = None
    l3_hangup_enabled: bool | None = None
    contact_freq_max: int | None = Field(None, ge=1, le=30)
    retention_days: int | None = Field(None, ge=30, le=3650)
    notify_quota_warning: bool | None = None
    notify_script_disabled: bool | None = None
    notify_work_order_completed: bool | None = None
    notify_case_escalated: bool | None = None
    notify_promise_expiring: bool | None = None
    notify_channels: list[NotifyChannel] | None = None
