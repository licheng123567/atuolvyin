"""Sprint 8.5 / 12.3 — Tenant settings schemas (PRD §3.14 / §L412)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

NotifyChannel = Literal["system", "sms", "wechat", "dingtalk"]


class TenantSettingsOut(BaseModel):
    recording_mode: Literal["live", "post", "auto"]
    l3_hangup_enabled: bool
    contact_freq_max: int
    retention_days: int
    # v1.6 — 本金打折审批策略
    discount_auto_approve_threshold_pct: int = 10
    discount_supervisor_max_pct: int = 30
    discount_disabled: bool = False
    # v1.6.2 — 滞纳金减免审批策略（独立于本金打折，默认更宽松）
    late_fee_waive_auto_approve_threshold_pct: int = 50
    late_fee_waive_supervisor_max_pct: int = 100
    late_fee_waive_disabled: bool = False
    # Sprint 12.3 — 通知规则
    notify_quota_warning: bool = True
    notify_script_disabled: bool = True
    notify_work_order_completed: bool = True
    notify_case_escalated: bool = True
    notify_promise_expiring: bool = True
    notify_channels: list[NotifyChannel] = ["system"]
    # v0.9.0 — N 天未联系自动释放公海(0 = 关闭)
    auto_release_stale_days: int = 0


class TenantSettingsUpdate(BaseModel):
    recording_mode: Literal["live", "post", "auto"] | None = None
    l3_hangup_enabled: bool | None = None
    contact_freq_max: int | None = Field(None, ge=1, le=30)
    retention_days: int | None = Field(None, ge=30, le=3650)
    discount_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    discount_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    discount_disabled: bool | None = None
    # v1.6.2 — 滞纳金减免独立策略
    late_fee_waive_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_disabled: bool | None = None
    notify_quota_warning: bool | None = None
    notify_script_disabled: bool | None = None
    notify_work_order_completed: bool | None = None
    notify_case_escalated: bool | None = None
    notify_promise_expiring: bool | None = None
    notify_channels: list[NotifyChannel] | None = None
    # v0.9.0 — 自动释放阈值
    auto_release_stale_days: int | None = Field(None, ge=0, le=180)

    @model_validator(mode="after")
    def _check_thresholds(self) -> TenantSettingsUpdate:
        a = self.discount_auto_approve_threshold_pct
        s = self.discount_supervisor_max_pct
        if a is not None and s is not None and a > s:
            raise ValueError(
                "discount_auto_approve_threshold_pct 不可超过 discount_supervisor_max_pct"
            )
        la = self.late_fee_waive_auto_approve_threshold_pct
        ls = self.late_fee_waive_supervisor_max_pct
        if la is not None and ls is not None and la > ls:
            raise ValueError(
                "late_fee_waive_auto_approve_threshold_pct 不可超过 late_fee_waive_supervisor_max_pct"
            )
        return self


# v0.9.0 — 服务商 Settings(v1.0.0 扩展对齐 TenantSettings 3 类)
class ProviderSettingsOut(BaseModel):
    auto_release_stale_days: int = 0
    # v1.0.0 — 与 TenantSettings 对齐(录音 / 频次 / 通知)
    recording_mode: Literal["live", "post", "auto"] = "auto"
    contact_freq_max: int = 3
    notify_quota_warning: bool = True
    notify_script_disabled: bool = True
    notify_work_order_completed: bool = True
    notify_case_escalated: bool = True
    notify_promise_expiring: bool = True
    notify_channels: list[NotifyChannel] = ["system"]


class ProviderSettingsUpdate(BaseModel):
    auto_release_stale_days: int | None = Field(None, ge=0, le=180)
    recording_mode: Literal["live", "post", "auto"] | None = None
    contact_freq_max: int | None = Field(None, ge=1, le=30)
    notify_quota_warning: bool | None = None
    notify_script_disabled: bool | None = None
    notify_work_order_completed: bool | None = None
    notify_case_escalated: bool | None = None
    notify_promise_expiring: bool | None = None
    notify_channels: list[NotifyChannel] | None = None
