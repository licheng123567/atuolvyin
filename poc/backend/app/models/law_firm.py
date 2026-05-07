"""Sprint 16.2 — 律所池 + 律师 (PRD §20.4 法务转化通道)。

平台运营维护合作律所池；分单时从该池中选取律所和律师，
denormalize 名字到 LegalConversionOrder.assigned_law_firm/assigned_lawyer_name 便于审计。
"""
from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LawFirm(Base, TimestampMixin):
    __tablename__ = "law_firm"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    license_no: Mapped[str | None] = mapped_column(sa.String(64))
    region: Mapped[str | None] = mapped_column(sa.String(64))
    contact_name: Mapped[str | None] = mapped_column(sa.String(120))
    contact_phone: Mapped[str | None] = mapped_column(sa.String(32))
    address: Mapped[str | None] = mapped_column(sa.String(300))
    specialties: Mapped[list[str] | None] = mapped_column(ARRAY(sa.Text))
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    accepting_orders: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True
    )
    rating_avg: Mapped[Decimal] = mapped_column(
        sa.Numeric(3, 2), nullable=False, default=Decimal("5.00")
    )
    completed_orders: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        sa.UniqueConstraint("license_no", name="uq_law_firm_license_no"),
        sa.Index("ix_law_firm_enabled", "enabled", "accepting_orders"),
    )


class LawFirmLawyer(Base, TimestampMixin):
    __tablename__ = "law_firm_lawyer"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    law_firm_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("law_firm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    license_no: Mapped[str | None] = mapped_column(sa.String(64))
    phone: Mapped[str | None] = mapped_column(sa.String(32))
    specialties: Mapped[list[str] | None] = mapped_column(ARRAY(sa.Text))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        sa.Index("ix_law_firm_lawyer_active", "law_firm_id", "is_active"),
    )
