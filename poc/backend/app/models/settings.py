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
    l3_hangup_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )
    contact_freq_max: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=3
    )
    retention_days: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=365
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
    )
