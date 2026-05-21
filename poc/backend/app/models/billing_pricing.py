"""v0.5.9 — 平台单价配置(单例,跨租户共享)。

设计:
- 单例表(`is_active=True` 最多 1 行;切换价格走「新增 + 旧的设 inactive」流程)
- 字段直接列出 4 个核心单价(分钟实时/事后 + 存证单次/案件包),不抽象成 key-value
  因为种类有限、查询时直接拿单行最快
- 后续若要按租户差异化,可加 tenant_id 列 + 唯一约束 (tenant_id, is_active)

参考 PRD §20.1.1 / §20.3:
- 实时分钟 ¥0.5
- 事后分钟 ¥0.3
- 存证单次(call/transcript/analysis) ¥5
- 存证案件级 bundle(evidence_bundle) ¥99
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BillingPricing(Base, TimestampMixin):
    __tablename__ = "billing_pricing"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    minute_price_live: Mapped[Decimal] = mapped_column(
        sa.Numeric(6, 4), nullable=False, default=Decimal("0.5"),
    )
    minute_price_post: Mapped[Decimal] = mapped_column(
        sa.Numeric(6, 4), nullable=False, default=Decimal("0.3"),
    )
    blockchain_price_per_attestation: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False, default=Decimal("5"),
    )
    blockchain_price_per_case_bundle: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False, default=Decimal("99"),
    )
    effective_from: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        # 至多一行 active(应用层保证;DB 加 partial unique index)
        sa.Index(
            "uq_billing_pricing_active", "is_active",
            unique=True, postgresql_where=sa.text("is_active = true"),
        ),
    )
