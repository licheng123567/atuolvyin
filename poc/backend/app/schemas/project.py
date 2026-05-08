"""Sprint 16.2 — Project (物业项目) schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChargePeriod = Literal["monthly", "quarterly", "semiannual", "annual"]
ContractType = Literal["preliminary_service", "elected", "re_elected", "interim_management"]


class ProjectCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    property_pm_user_id: int | None = None
    # DEPRECATED v1.5.6 — 服务商 PM 由服务商 admin 自家指派，物业端忽略入参
    provider_pm_user_id: int | None = None
    provider_id: int | None = None
    plan_start: datetime | None = None
    plan_end: datetime | None = None
    description: str | None = None
    allow_internal_assist: bool = False  # DEPRECATED v1.5.6
    # v1.5 S18.5 — 项目团队（督导组 + 默认催收员），创建时一次性写入 ProjectMember
    # v1.5.6 — 仅自办项目（无 provider_id）有效；外包项目由 ProjectCreateIn 校验拒绝
    supervisor_user_ids: list[int] = []
    agent_user_ids: list[int] = []
    # v1.5.6 — 任意项目都必选「物业协调员」绑定（单选，接此项目的工单）
    coordinator_user_id: int | None = None
    # v1.5.6 — 任意项目都必选「法务对接人」绑定（单选，处理此项目的法务转化）
    legal_user_id: int | None = None
    # v1.6 — 项目收费 + 合同信息
    charge_rate_per_sqm: Decimal | None = Field(None, ge=0, le=999.9999)
    # v1.6.2 — 自由文本（多行），描述商铺/住宅/车位等不同收费标准
    charge_rate_text: str | None = Field(None, max_length=2000)
    charge_period: ChargePeriod | None = None
    contract_type: ContractType | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_attachment_key: str | None = Field(None, max_length=500)
    contract_attachment_filename: str | None = Field(None, max_length=255)
    charge_notes: str | None = Field(None, max_length=1000)
    # v1.6.1 — 项目级「本金打折」阈值（NULL 继承 TenantSettings）
    discount_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    discount_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    discount_disabled: bool | None = None
    # v1.6.2 — 项目级「滞纳金减免」阈值（独立于本金打折）
    late_fee_waive_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_disabled: bool | None = None


class ProjectUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    property_pm_user_id: int | None = None
    # DEPRECATED v1.5.6 — 服务商 PM 由服务商端指派；物业端 PATCH 时忽略
    provider_pm_user_id: int | None = None
    provider_id: int | None = None
    plan_start: datetime | None = None
    plan_end: datetime | None = None
    description: str | None = None
    status: str | None = Field(None, pattern=r"^(active|paused|closed)$")
    allow_internal_assist: bool | None = None  # DEPRECATED v1.5.6
    # v1.5.6 — 项目协调员 + 法务对接人（任意项目）
    coordinator_user_id: int | None = None
    legal_user_id: int | None = None
    # v1.6 — 项目收费 + 合同信息（patch 支持局部更新）
    charge_rate_per_sqm: Decimal | None = Field(None, ge=0, le=999.9999)
    charge_rate_text: str | None = Field(None, max_length=2000)
    charge_period: ChargePeriod | None = None
    contract_type: ContractType | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_attachment_key: str | None = Field(None, max_length=500)
    contract_attachment_filename: str | None = Field(None, max_length=255)
    charge_notes: str | None = Field(None, max_length=1000)
    # v1.6.1 — 项目级「本金打折」阈值
    discount_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    discount_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    discount_disabled: bool | None = None
    # v1.6.2 — 项目级「滞纳金减免」阈值
    late_fee_waive_auto_approve_threshold_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_supervisor_max_pct: int | None = Field(None, ge=0, le=100)
    late_fee_waive_disabled: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    provider_id: int | None
    provider_name: str | None = None
    property_pm_user_id: int | None
    property_pm_name: str | None = None
    provider_pm_user_id: int | None
    provider_pm_name: str | None = None
    plan_start: datetime | None
    plan_end: datetime | None
    status: str
    description: str | None
    allow_internal_assist: bool = False
    case_count: int = 0
    created_at: datetime
    # v1.5.6 — 项目协调员 + 法务对接人
    coordinator_user_id: int | None = None
    coordinator_name: str | None = None
    legal_user_id: int | None = None
    legal_name: str | None = None
    # v1.6 — 项目收费 + 合同信息
    charge_rate_per_sqm: Decimal | None = None
    charge_rate_text: str | None = None
    charge_period: ChargePeriod | None = None
    contract_type: ContractType | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_attachment_key: str | None = None
    contract_attachment_filename: str | None = None
    charge_notes: str | None = None
    # v1.6.1 — 项目级「本金打折」阈值（NULL 表示继承 TenantSettings）
    discount_auto_approve_threshold_pct: int | None = None
    discount_supervisor_max_pct: int | None = None
    discount_disabled: bool | None = None
    # v1.6.2 — 项目级「滞纳金减免」阈值（独立策略）
    late_fee_waive_auto_approve_threshold_pct: int | None = None
    late_fee_waive_supervisor_max_pct: int | None = None
    late_fee_waive_disabled: bool | None = None
