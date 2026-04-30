from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DeviceProfile(Base):
    __tablename__ = "device_profile"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    device_id: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    brand: Mapped[Optional[str]] = mapped_column(sa.Text)
    model: Mapped[Optional[str]] = mapped_column(sa.Text)
    os_version: Mapped[Optional[str]] = mapped_column(sa.Text)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    is_healthy: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("idx_device_profile_tenant_user", "tenant_id", "user_id"),
    )
