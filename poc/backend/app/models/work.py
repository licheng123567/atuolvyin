from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    case_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("collection_case.id"))
    call_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("call_record.id"))
    order_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )  # quality / reduction / dispute / other
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="open")
    # v1.6 — 4 档优先级（urgent_critical/urgent/normal/low），CHECK 约束在 DB 层
    priority: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="normal")
    resolution: Mapped[str | None] = mapped_column(sa.Text)


class LegalCase(Base, TimestampMixin):
    __tablename__ = "legal_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("collection_case.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, default="pending_eval")
    amount_disputed: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(12, 2))
    lawyer_name: Mapped[str | None] = mapped_column(sa.Text)
    law_firm: Mapped[str | None] = mapped_column(sa.Text)
    next_milestone: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)
