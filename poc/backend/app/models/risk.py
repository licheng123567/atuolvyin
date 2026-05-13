from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class RiskKeyword(Base, TimestampMixin):
    __tablename__ = "risk_keyword"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    speaker: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    level: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    keyword: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "category", "keyword", name="uq_risk_keyword_tenant_cat_kw"
        ),
        sa.Index(
            "idx_riskkw_tenant_cat_speaker_active", "tenant_id", "category", "speaker", "is_active"
        ),
    )
