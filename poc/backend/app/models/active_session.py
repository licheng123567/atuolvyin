"""Sprint 15.1 — 多设备登录踢出 ActiveSession 表 (PRD §11.5).

每个 (user_id, device_type) 唯一一行，存当前 active 的 token_hash。
新设备登录 → upsert 覆盖旧 hash → 旧 token 下次请求时 hash 不匹配 → 401 ERR_SESSION_EVICTED。

PC + App 互相独立计算（device_type 不同 → 各占一行，两端可同时在线）。
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ActiveSession(Base):
    __tablename__ = "active_session"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_type: Mapped[str] = mapped_column(sa.String(8), nullable=False)  # pc | app
    token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # sha256(jwt)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "device_type", name="uq_active_session_user_device"),
        sa.CheckConstraint("device_type IN ('pc','app')", name="ck_active_session_device_type"),
    )
