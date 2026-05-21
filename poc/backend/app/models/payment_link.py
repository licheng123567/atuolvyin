"""v2.2 — 缴费链接 token 持久化（业主 H5 账单页凭 token 查案件）。"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class PaymentLink(Base, TimestampMixin):
    __tablename__ = "payment_link"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("project.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    payment_mode: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="property_self"
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "payment_mode IN ('property_self','notary_escrow')",
            name="ck_payment_link_payment_mode",
        ),
    )
