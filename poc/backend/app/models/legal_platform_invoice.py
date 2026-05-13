"""Sprint 16.3 — 律所→平台介绍费账单 (PRD §20.4)。

完成的 LegalConversionOrder 会冻结一笔 platform_fee_amount。
按月聚合一家律所的所有 completed 订单 → DRAFT 账单 → 平台 ops 确认 →
律所付款 → 标记 PAID。

invoice_lines 字段冗余存订单 id 列表，便于审计追溯。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LegalPlatformInvoice(Base, TimestampMixin):
    __tablename__ = "legal_platform_invoice"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    law_firm_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("law_firm.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    invoice_lines: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="DRAFT")
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    payment_proof_url: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','PAID','CANCELLED')",
            name="ck_legal_invoice_status",
        ),
        sa.UniqueConstraint(
            "law_firm_id",
            "period_start",
            "period_end",
            name="uq_legal_invoice_firm_period",
        ),
        sa.Index("ix_legal_invoice_firm_status", "law_firm_id", "status"),
    )
