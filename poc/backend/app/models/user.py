from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserAccount(Base, TimestampMixin):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)  # AES-256
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))


class PlatformOpsAssignment(Base, TimestampMixin):
    __tablename__ = "platform_ops_assignment"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    ops_user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # tenant / provider
    entity_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
