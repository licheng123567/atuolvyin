"""v1.6 — supervisor_shift 表（督导值班排班持久化）。

替代 supervisor_shifts.py 中的 in-memory _SHIFT_STORE。
每行一个 (tenant_id, date, slot) 唯一组合 → supervisor_user_id。
"""

from __future__ import annotations

from datetime import date as date_type

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SupervisorShift(Base, TimestampMixin):
    __tablename__ = "supervisor_shift"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_date: Mapped[date_type] = mapped_column(sa.Date, nullable=False)
    slot: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    supervisor_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="SET NULL"),
    )
    supervisor_name: Mapped[str | None] = mapped_column(sa.String(120))
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_supervisor_shift_slot",
        ),
        sa.Index("ix_supervisor_shift_tenant_date", "tenant_id", "shift_date"),
        sa.Index("ix_supervisor_shift_provider_id", "provider_id"),
        # 物业侧（provider_id IS NULL）唯一：tenant + date + slot
        sa.Index(
            "uq_supervisor_shift_property",
            "tenant_id", "shift_date", "slot",
            unique=True,
            postgresql_where=sa.text("provider_id IS NULL"),
        ),
        # 服务商侧（provider_id 非空）唯一：tenant + provider + date + slot
        sa.Index(
            "uq_supervisor_shift_provider",
            "tenant_id", "provider_id", "shift_date", "slot",
            unique=True,
            postgresql_where=sa.text("provider_id IS NOT NULL"),
        ),
    )


class SupervisorShiftSwapRequest(Base, TimestampMixin):
    __tablename__ = "supervisor_shift_swap_request"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_user_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    to_user_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    shift_date: Mapped[date_type] = mapped_column(sa.Date, nullable=False)
    slot: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending_confirm")
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_swap_request_slot",
        ),
        sa.CheckConstraint(
            "status IN ('pending_confirm', 'accepted', 'rejected', 'cancelled')",
            name="ck_swap_request_status",
        ),
        sa.Index("ix_supervisor_shift_swap_request_provider_id", "provider_id"),
    )
