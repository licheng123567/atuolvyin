from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScriptTemplate(Base):
    __tablename__ = "script_template"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    usage_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    adoption_rate: Mapped[Optional[float]] = mapped_column(sa.Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(sa.Float)
    score_grade: Mapped[Optional[str]] = mapped_column(sa.String(1))
    created_by: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("user_account.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("idx_script_template_tenant", "tenant_id"),
        sa.Index("idx_script_template_active", "tenant_id", "is_active"),
    )


class ScriptTemplateVersion(Base):
    __tablename__ = "script_template_version"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    script_template_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("script_template.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    edited_by: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("user_account.id"), nullable=True
    )
    edited_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("script_template_id", "version", name="uq_script_version"),
    )


class TenantSuggestionConfig(Base):
    __tablename__ = "tenant_suggestion_config"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    sensitivity: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    max_per_push: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )
