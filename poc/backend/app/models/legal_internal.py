"""v1.9.0 — 物业内部法务处理环节相关模型。

3 张新表：
- LegalInternalAction：法务转化订单的内部处理流水（沟通/律师函/调解等多次操作）
- InternalLegalLetterTemplate：物业 admin 自管的律师函/催告函模板
- PartnerLawFirm：物业 admin 自管的合作律所列表（不耦合现有 LawFirm，那个是平台级撮合用）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LegalInternalAction(Base, TimestampMixin):
    """物业内部法务对法务订单的一次操作。"""

    __tablename__ = "legal_internal_action"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    legal_order_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_conversion_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    note: Mapped[str | None] = mapped_column(sa.Text)
    # v1.9.0 — 关联律师函模板（仅 send_lawyer_letter / send_notice 才用）
    letter_template_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("internal_legal_letter_template.id", ondelete="SET NULL"),
    )
    # 关联合作律所（仅签发律师函时用）
    partner_law_firm_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("partner_law_firm.id", ondelete="SET NULL"),
    )
    # 附件（盖章版律师函 PDF / 调解协议等）
    attachment_key: Mapped[str | None] = mapped_column(sa.String(512))
    attachment_filename: Mapped[str | None] = mapped_column(sa.String(255))
    # 律师函起草时填的变量（jsonb）
    letter_variables: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        sa.CheckConstraint(
            "action_type IN ('contact_owner','send_lawyer_letter','send_notice',"
            "'mediation','other')",
            name="ck_legal_internal_action_type",
        ),
        sa.Index("ix_legal_internal_action_order", "legal_order_id", "occurred_at"),
    )


class InternalLegalLetterTemplate(Base, TimestampMixin):
    """物业 admin 自管的律师函/催告函模板。"""

    __tablename__ = "internal_legal_letter_template"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    body_md: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # variables: [{"name":"owner_name","label":"业主姓名","type":"string","required":true}, ...]
    variables: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        sa.CheckConstraint(
            "category IN ('lawyer_letter','notice','reminder','other')",
            name="ck_internal_letter_template_category",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_internal_letter_template_name"),
    )


class PartnerLawFirm(Base, TimestampMixin):
    """物业 admin 自管的合作律所简表（独立于平台级 LawFirm）。"""

    __tablename__ = "partner_law_firm"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(sa.String(120))
    # AES-256 加密；展示时按 v1.7.0 规则脱敏（这里不属业主电话，admin 永久看明文）
    contact_phone_enc: Mapped[str | None] = mapped_column(sa.Text)
    contact_email: Mapped[str | None] = mapped_column(sa.String(200))
    # 律所盖章 PDF/PNG（用于电子签发律师函时叠章）
    seal_attachment_key: Mapped[str | None] = mapped_column(sa.String(512))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (sa.UniqueConstraint("tenant_id", "name", name="uq_partner_law_firm_name"),)
