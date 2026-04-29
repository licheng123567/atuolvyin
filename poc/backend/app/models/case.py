from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class OwnerProfile(Base, TimestampMixin):
    __tablename__ = "owner_profile"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)  # AES-256
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)  # SHA-256 防篡改预埋
    building: Mapped[Optional[str]] = mapped_column(sa.Text)
    room: Mapped[Optional[str]] = mapped_column(sa.Text)
    tags: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), default=list)
    do_not_call: Mapped[bool] = mapped_column(sa.Boolean, default=False)


class Project(Base, TimestampMixin):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    project_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # collection / vote
    provider_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("service_provider.id")
    )
    property_pm_user_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id")
    )
    provider_pm_user_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id")
    )
    plan_start: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    plan_end: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")
    description: Mapped[Optional[str]] = mapped_column(sa.Text)


class CollectionCase(Base, TimestampMixin):
    __tablename__ = "collection_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("project.id")
    )
    owner_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("owner_profile.id"), nullable=False
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id")
    )
    pool_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="public")
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, default="new")
    amount_owed: Mapped[Optional[sa.Numeric]] = mapped_column(sa.Numeric(12, 2))
    months_overdue: Mapped[Optional[int]] = mapped_column(sa.Integer)
    priority_score: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    monthly_contact_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")

    __table_args__ = (
        sa.Index("idx_case_tenant_pool", "tenant_id", "pool_type"),
        sa.Index("idx_case_tenant_assigned", "tenant_id", "assigned_to"),
    )
