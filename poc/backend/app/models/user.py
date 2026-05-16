from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserAccount(Base, TimestampMixin):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)  # AES-256
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # v1.4 S17.4 — 邮箱二登录入口（组织管理员）
    email: Mapped[str | None] = mapped_column(sa.String(120), unique=True)
    login_method: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="phone"
    )  # phone / email / otp
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Sprint 14.3 — 个人偏好 JSON（首次登录引导是否已关闭、UI 偏好等）
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"), default=dict
    )
    # v2.2 角色重构 — 平台身份(superadmin / ops),非平台用户为 NULL
    platform_role: Mapped[str | None] = mapped_column(sa.String(16))


class PlatformOpsAssignment(Base, TimestampMixin):
    __tablename__ = "platform_ops_assignment"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    ops_user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # tenant / provider
    entity_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text)
