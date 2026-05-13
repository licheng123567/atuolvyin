"""Sprint 16.4 — 法律文书模板 + 渲染产物 (PRD §20.4)。

每个 LegalServicePackage.package_type 对应一份默认模板（律师函/调解通知/
诉状大纲/代理委托），可被租户级模板覆盖。

LegalDocumentRender 是某次生成产物（每个订单可重生成多次，按 version 递增）。
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LegalDocumentTemplate(Base, TimestampMixin):
    __tablename__ = "legal_document_template"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    package_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body_md: Mapped[str] = mapped_column(sa.Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)

    __table_args__ = (
        sa.CheckConstraint(
            "package_type IN ('lawyer_letter','mediation','small_claims','full_agency')",
            name="ck_legal_doc_tpl_pkg_type",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "package_type",
            "slug",
            name="uq_legal_doc_tpl_tenant_pkg_slug",
        ),
    )


class LegalDocumentRender(Base, TimestampMixin):
    __tablename__ = "legal_document_render"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_conversion_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_document_template.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body_md: Mapped[str] = mapped_column(sa.Text, nullable=False)
    rendered_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    rendered_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)

    __table_args__ = (sa.Index("ix_legal_doc_render_order_version", "order_id", "version"),)
