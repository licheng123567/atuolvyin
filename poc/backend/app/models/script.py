from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScriptTemplate(Base):
    __tablename__ = "script_template"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True
    )  # None = platform-level shared template
    # v1.4 S16.5 — 三层归属：
    #   tenant_id NULL & provider_id NULL → 平台预置
    #   tenant_id NOT NULL & provider_id NULL → 物业私有
    #   provider_id NOT NULL → 服务商私有
    provider_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
        nullable=True,
    )
    # v1.5.7 — 项目级生效范围：
    #   project_id NULL → 本物业（或本服务商）全项目通用
    #   project_id NOT NULL → 仅指定项目可见
    project_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    # v1.5 S18.6 — 通话场景维度：opening/objection_handling/promise_confirm/closing
    scene: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="objection_handling"
    )
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
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
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
        sa.Index("idx_script_template_provider", "provider_id"),
        sa.Index("idx_script_template_scene", "scene"),
        sa.CheckConstraint("score_grade IN ('A','B','C','D')", name="ck_st_score_grade"),
        sa.CheckConstraint(
            "scene IN ('opening','objection_handling','promise_confirm','closing')",
            name="ck_script_template_scene",
        ),
    )


class ScriptTemplateVersion(Base):
    __tablename__ = "script_template_version"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    script_template_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("script_template.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    edited_by: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )
    edited_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("script_template_id", "version", name="uq_script_version"),
    )


class TenantSuggestionConfig(Base):
    __tablename__ = "tenant_suggestion_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    sensitivity: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    max_per_push: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint("sensitivity BETWEEN 1 AND 5", name="ck_tsc_sensitivity"),
        sa.CheckConstraint("max_per_push BETWEEN 1 AND 10", name="ck_tsc_max_per_push"),
    )
