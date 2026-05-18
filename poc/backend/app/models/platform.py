"""Sprint 10 — Platform-level extras.

CustomerFollowup：平台运营员对租户客户的跟进记录（电话/邮件备注）。
SystemAnnouncement：平台公告，可指定受众（all / role:admin / tenant:123）。
LLMPromptTemplate：超管管理的 LLM 基础 Prompt 模板（版本化）。
BlockchainConfig：单例配置，区块链存证合作方信息（API key AES 加密）。
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CustomerFollowup(Base, TimestampMixin):
    __tablename__ = "customer_followup"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False, index=True
    )
    note: Mapped[str] = mapped_column(sa.Text, nullable=False)
    follow_up_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )  # next planned check-in
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )


class SystemAnnouncement(Base, TimestampMixin):
    __tablename__ = "system_announcement"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    audience: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, default="all"
    )  # all / role:admin / tenant:123
    publish_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )  # NULL = draft, future = scheduled, past = published
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )


class LLMPromptTemplate(Base, TimestampMixin):
    __tablename__ = "llm_prompt_template"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )

    __table_args__ = (sa.UniqueConstraint("name", "version", name="uq_llm_prompt_name_version"),)


class BlockchainConfig(Base):
    __tablename__ = "blockchain_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(
        sa.String(64), nullable=False
    )  # antchain / fisco-bcos / mock
    api_endpoint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # AES-256
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (sa.UniqueConstraint("provider", name="uq_blockchain_config_provider"),)


class SmsConfig(Base):
    """短信中心（028lk）平台级配置 —— 单行，超管在 /super/sms-config 维护。"""

    __tablename__ = "sms_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    secret_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    secret_key_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # AES-256
    sign_name: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    otp_template_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
