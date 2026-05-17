from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class OwnerProfile(Base, TimestampMixin):
    __tablename__ = "owner_profile"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)  # AES-256
    data_hash: Mapped[str | None] = mapped_column(sa.Text)  # SHA-256 防篡改预埋
    building: Mapped[str | None] = mapped_column(sa.Text)
    room: Mapped[str | None] = mapped_column(sa.Text)
    tags: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), default=list)
    do_not_call: Mapped[bool] = mapped_column(sa.Boolean, default=False)


class Project(Base, TimestampMixin):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("service_provider.id")
    )
    property_pm_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id")
    )
    provider_pm_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id")
    )
    plan_start: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    plan_end: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")
    description: Mapped[str | None] = mapped_column(sa.Text)
    # DEPRECATED v1.5.6 — 混合协助模式已废弃（项目要么自办要么外包，二选一）
    # 字段保留以兼容旧数据 / API 客户端；代码层面所有判断都视作 False
    # v1.6 表清理时统一删除
    allow_internal_assist: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    # v1.6 — 项目收费 + 合同信息（用户反馈：创建项目应录入收费标准 / 时间约定 / 合同）
    charge_rate_per_sqm: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(8, 4)
    )  # DEPRECATED v1.6.2 — 改为自由文本 charge_rate_text；保留以兼容历史数据
    # v1.6.2 — 自由文本（支持多行，描述商铺 / 住宅 / 车位等不同收费标准）
    charge_rate_text: Mapped[str | None] = mapped_column(sa.Text)
    charge_period: Mapped[str | None] = mapped_column(sa.String(16))
    # monthly / quarterly / semiannual / annual
    contract_type: Mapped[str | None] = mapped_column(sa.String(32))
    # preliminary_service / elected / re_elected / interim_management
    contract_start_date: Mapped[date | None] = mapped_column(sa.Date)
    contract_end_date: Mapped[date | None] = mapped_column(sa.Date)
    contract_attachment_key: Mapped[str | None] = mapped_column(sa.Text)
    # MinIO object_key 指向上传的合同 PDF
    contract_attachment_filename: Mapped[str | None] = mapped_column(sa.Text)
    # v1.6.2 — 上传时的原始文件名（用于下载展示）
    charge_notes: Mapped[str | None] = mapped_column(sa.Text)
    # 收费规则备注（如：商铺 3.0/㎡，住宅 1.5/㎡）

    # v1.6.1 — 项目级减免阈值（NULL 时继承 TenantSettings；不同项目可有不同政策）
    # v1.6.2 — 拆分为两类：本金打折 + 滞纳金减免（pricinpal_discount_* + late_fee_waive_*）
    # 旧字段保留作为「本金打折」别名（discount_* == principal_discount_*），下版本清理
    discount_auto_approve_threshold_pct: Mapped[int | None] = mapped_column(sa.SmallInteger)
    discount_supervisor_max_pct: Mapped[int | None] = mapped_column(sa.SmallInteger)
    discount_disabled: Mapped[bool | None] = mapped_column(sa.Boolean)
    # v1.6.2 — 滞纳金减免（独立策略；多数物业愿意减免滞纳金）
    late_fee_waive_auto_approve_threshold_pct: Mapped[int | None] = mapped_column(sa.SmallInteger)
    late_fee_waive_supervisor_max_pct: Mapped[int | None] = mapped_column(sa.SmallInteger)
    late_fee_waive_disabled: Mapped[bool | None] = mapped_column(sa.Boolean)

    # §9.2 D1/D2 — 项目级佣金率（NUMERIC(6,4)，NULL 时回退系统默认 0.05）
    internal_agent_commission_rate: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(6, 4))
    provider_agent_commission_rate: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(6, 4))

    __table_args__ = (
        sa.CheckConstraint(
            "charge_period IS NULL OR charge_period IN ('monthly','quarterly','semiannual','annual')",
            name="ck_project_charge_period",
        ),
        sa.CheckConstraint(
            "contract_type IS NULL OR contract_type IN ('preliminary_service','elected','re_elected','interim_management')",
            name="ck_project_contract_type",
        ),
        sa.CheckConstraint(
            "discount_auto_approve_threshold_pct IS NULL OR discount_auto_approve_threshold_pct BETWEEN 0 AND 100",
            name="ck_project_discount_auto_threshold",
        ),
        sa.CheckConstraint(
            "discount_supervisor_max_pct IS NULL OR discount_supervisor_max_pct BETWEEN 0 AND 100",
            name="ck_project_discount_supervisor_max",
        ),
        sa.CheckConstraint(
            "discount_auto_approve_threshold_pct IS NULL OR discount_supervisor_max_pct IS NULL OR discount_auto_approve_threshold_pct <= discount_supervisor_max_pct",
            name="ck_project_discount_thresholds_order",
        ),
        sa.CheckConstraint(
            "late_fee_waive_auto_approve_threshold_pct IS NULL OR late_fee_waive_auto_approve_threshold_pct BETWEEN 0 AND 100",
            name="ck_project_late_fee_waive_auto_threshold",
        ),
        sa.CheckConstraint(
            "late_fee_waive_supervisor_max_pct IS NULL OR late_fee_waive_supervisor_max_pct BETWEEN 0 AND 100",
            name="ck_project_late_fee_waive_supervisor_max",
        ),
        sa.CheckConstraint(
            "late_fee_waive_auto_approve_threshold_pct IS NULL OR late_fee_waive_supervisor_max_pct IS NULL OR late_fee_waive_auto_approve_threshold_pct <= late_fee_waive_supervisor_max_pct",
            name="ck_project_late_fee_waive_thresholds_order",
        ),
    )


class CollectionCase(Base, TimestampMixin):
    __tablename__ = "collection_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    project_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("project.id"))
    owner_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("owner_profile.id"), nullable=False
    )
    assigned_to: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    pool_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="public")
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, default="new")
    amount_owed: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(12, 2))
    months_overdue: Mapped[int | None] = mapped_column(sa.Integer)
    # v1.6 — 账单透明化：导入时按账单起止日 + 本金 + 滞纳金；详情页按月平均推算明细
    bill_period_start: Mapped[date | None] = mapped_column(sa.Date)
    bill_period_end: Mapped[date | None] = mapped_column(sa.Date)
    principal_amount: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(12, 2))
    late_fee_amount: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(12, 2))
    arrears_reason: Mapped[str | None] = mapped_column(sa.Text)
    # 业主欠费理由（导入时录入）：经济困难 / 服务质量异议 / 房屋空置 / 其他
    priority_score: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_contact_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    monthly_contact_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    # v1.6 承诺还款到期时间，到期前 24h scan_and_notify_promise_expiring 会发提醒
    promise_due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    data_hash: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")
    # v1.4 — 欠费情况说明（导入时录入，让催收员一眼看到原因）
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.Index("idx_case_tenant_pool", "tenant_id", "pool_type"),
        sa.Index("idx_case_tenant_assigned", "tenant_id", "assigned_to"),
    )
