from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    credit_code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    admin_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)  # AES-256
    plan: Mapped[str] = mapped_column(sa.Text, nullable=False, default="trial")
    expires_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    monthly_minute_quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    minute_quota_updated_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)

    memberships: Mapped[list[UserTenantMembership]] = relationship(back_populates="tenant")


class ServiceProvider(Base, TimestampMixin):
    __tablename__ = "service_provider"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )  # legal / collection / both
    admin_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)
    monthly_minute_quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)


class ProviderTenantContract(Base, TimestampMixin):
    __tablename__ = "provider_tenant_contract"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    provider_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("service_provider.id"), nullable=False
    )
    signed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    service_types: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")


class TenantMinuteUsage(Base):
    __tablename__ = "tenant_minute_usage"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    year_month: Mapped[str] = mapped_column(sa.Text, nullable=False)  # "2026-04"
    used_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    quota_at_time: Mapped[Optional[int]] = mapped_column(sa.Integer)

    __table_args__ = (sa.UniqueConstraint("tenant_id", "year_month"),)


class UserTenantMembership(Base, TimestampMixin):
    __tablename__ = "user_tenant_membership"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="INTERNAL")
    provider_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("service_provider.id")
    )
    quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    expire_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    access_hours: Mapped[Optional[str]] = mapped_column(sa.Text)  # "09:00-18:00"
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
