from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SettlementStatement(Base, TimestampMixin):
    __tablename__ = "settlement_statement"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("provider_tenant_contract.id"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    total_amount: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(12, 2), nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(
        sa.Text, nullable=False, default="DRAFT"
    )  # DRAFT/CONFIRMED/PAID/DISPUTED
    payment_proof_url: Mapped[str | None] = mapped_column(sa.Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','PAID','DISPUTED')", name="ck_settlement_status"
        ),
    )


class DisputeRecord(Base, TimestampMixin):
    __tablename__ = "dispute_record"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    statement_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("settlement_statement.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(sa.Text)
    submitted_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
