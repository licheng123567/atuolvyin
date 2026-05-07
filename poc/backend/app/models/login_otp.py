"""v1.4 S17.4 — Login / password-reset OTP storage."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class LoginOtp(Base):
    __tablename__ = "login_otp"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    purpose: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="login"
    )  # login / password_reset
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("idx_login_otp_phone", "phone_enc", "purpose"),
    )
