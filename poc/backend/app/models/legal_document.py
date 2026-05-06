"""Sprint 11.6 — LegalDocument (PRD §L2136).

法务为某 LegalCase 上传 / 分类 / 维护的法律文件（合同 / 判决书 / 通知 /
证据材料 / 其他）。文件本体走 storage 层（local / minio / oss），DB 只存元数据。
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LegalDocument(Base, TimestampMixin):
    __tablename__ = "legal_document"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False, index=True
    )
    legal_case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="other"
    )  # contract / judgment / notice / evidence / other
    object_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(sa.String(100))
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    uploaded_by: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.CheckConstraint(
            "category IN ('contract','judgment','notice','evidence','other')",
            name="ck_legal_document_category",
        ),
    )
