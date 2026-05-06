"""Sprint 15 — platform-level audit log + plan config models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AuditLog(Base):
    """Platform-level audit log capturing actions by ops/super users.

    `tenant_id` is nullable: NULL means a platform-level action (e.g. tenant.create
    where tenant_id is the *target*, not the actor's own tenant).
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    target_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class PlanConfig(Base, TimestampMixin):
    """SaaS plan catalog — display name, monthly minutes, price, features."""

    __tablename__ = "plan_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    plan_name: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    monthly_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Sprint 14.1 — 实时 vs 事后配额分别（PRD §20.1.1）
    # NULL 表示该套餐不区分（按 monthly_minutes 共用），非 NULL 时分别拦截
    monthly_realtime_minutes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    monthly_post_minutes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    price_monthly: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")
    )
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
