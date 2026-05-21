"""Sprint 8.5 / 12.3 — TenantSettings (PRD §3.14 / §L412).

物业管理员可调的合规与运营总开关：
- recording_mode: live (实时) / post (事后) / auto (按网络/CPU 自动降级)
- l3_hangup_enabled: 是否启用 L3 自动挂断
- contact_freq_max: 每月每个业主最多联系次数（用于风控提醒）
- retention_days: 录音/转写数据的保留天数

Sprint 12.3 — 通知规则（PRD §L412）：5 个具体事件 × 渠道数组的开关式配置。
事件类型源自 PRD 散落的具体触发点（L1682 / L1453 / §8.3 / L481 / L57），
不引入抽象 rule 引擎；事件的真实派发由后续 notification worker 消费这些字段。

每个租户最多一条；未配置时回退到 default。
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    recording_mode: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="auto"
    )  # live / post / auto
    l3_hangup_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    contact_freq_max: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    retention_days: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=365)

    # v1.6 — 协商打折 / 减免审批策略（admin 配置）
    # v1.6.2 — 拆分为「本金打折」+「滞纳金减免」两类（多数物业愿意减免滞纳金，但本金打折更严格）
    # 旧字段 discount_* 现等价于「本金打折」策略
    discount_auto_approve_threshold_pct: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=10, server_default=sa.text("10")
    )  # 本金打折 < X% 自动通过；0 = 不允许任何自动通过
    discount_supervisor_max_pct: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=30, server_default=sa.text("30")
    )  # 本金打折 ≤ X% 督导可批；> X% 转 admin
    discount_disabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )  # true 表示本租户完全禁用「本金打折」功能
    # v1.6.2 — 滞纳金减免（独立策略；默认更宽松：100% 督导可批）
    late_fee_waive_auto_approve_threshold_pct: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=50, server_default=sa.text("50")
    )  # 滞纳金减免 < X% 自动通过；默认 50%
    late_fee_waive_supervisor_max_pct: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=100, server_default=sa.text("100")
    )  # 滞纳金减免 ≤ X% 督导可批；默认 100%（即全部减）
    late_fee_waive_disabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )  # true 表示本租户禁用滞纳金减免功能

    # v1.6.9 — 公海池抢单上限：催收员同时持有未结案私海案件不超过此数
    public_pool_claim_max: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=50, server_default=sa.text("50")
    )

    # v0.9.0 — N 天未联系自动释放回公海(0 = 关闭功能,1-180 = 阈值)
    # 定时任务每日扫描:assigned_to IS NOT NULL + last_contact_at < now - N days
    # + stage IN (new/callback/contacting) → assigned_to=None + pool_type=public
    auto_release_stale_days: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default=sa.text("0")
    )

    # Sprint 12.3 — 通知规则 (PRD §L412)
    notify_quota_warning: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )  # 配额 80%/95%/100% 预警 (L1682)
    notify_script_disabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )  # D 级话术自动禁用 (L1453)
    notify_work_order_completed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )  # 工单处理完成通知催收员 (§8.3)
    notify_case_escalated: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )  # 大额案件升级通知主管 (L481)
    notify_promise_expiring: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )  # 承诺日期到期前提醒 (L57)
    notify_channels: Mapped[list[str]] = mapped_column(
        ARRAY(sa.String(16)),
        nullable=False,
        default=lambda: ["system"],
        server_default=sa.text("ARRAY['system']::varchar[]"),
    )  # ["system", "sms", "wechat", "dingtalk"]

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.CheckConstraint(
            "recording_mode IN ('live','post','auto')",
            name="ck_tenant_settings_recording_mode",
        ),
        sa.CheckConstraint(
            "contact_freq_max BETWEEN 1 AND 30",
            name="ck_tenant_settings_freq",
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 30 AND 3650",
            name="ck_tenant_settings_retention",
        ),
        sa.CheckConstraint(
            "discount_auto_approve_threshold_pct BETWEEN 0 AND 100",
            name="ck_tenant_settings_discount_auto_threshold",
        ),
        sa.CheckConstraint(
            "discount_supervisor_max_pct BETWEEN 0 AND 100",
            name="ck_tenant_settings_discount_supervisor_max",
        ),
        sa.CheckConstraint(
            "discount_auto_approve_threshold_pct <= discount_supervisor_max_pct",
            name="ck_tenant_settings_discount_thresholds_order",
        ),
        sa.CheckConstraint(
            "late_fee_waive_auto_approve_threshold_pct BETWEEN 0 AND 100",
            name="ck_tenant_settings_late_fee_waive_auto",
        ),
        sa.CheckConstraint(
            "late_fee_waive_supervisor_max_pct BETWEEN 0 AND 100",
            name="ck_tenant_settings_late_fee_waive_sup_max",
        ),
        sa.CheckConstraint(
            "late_fee_waive_auto_approve_threshold_pct <= late_fee_waive_supervisor_max_pct",
            name="ck_tenant_settings_late_fee_waive_order",
        ),
        sa.CheckConstraint(
            "public_pool_claim_max BETWEEN 1 AND 1000",
            name="ck_tenant_settings_pool_claim_max",
        ),
        sa.CheckConstraint(
            "auto_release_stale_days BETWEEN 0 AND 180",
            name="ck_tenant_settings_auto_release_stale_days",
        ),
    )


class ProviderSettings(Base):
    """v0.9.0 — 服务商级配置项。

    与 TenantSettings 对称(服务商 admin 设置作用于自家服务商接的项目案件)。
    当前仅含一个字段 auto_release_stale_days,后续可扩展。
    """

    __tablename__ = "provider_settings"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # N 天未联系自动释放回服务商内部公海(0 = 关闭,1-180 = 阈值)
    # 与物业侧等价但作用域是「服务商接的案件 + 服务商内催收员持有」
    auto_release_stale_days: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default=sa.text("0")
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.CheckConstraint(
            "auto_release_stale_days BETWEEN 0 AND 180",
            name="ck_provider_settings_auto_release_stale_days",
        ),
    )
