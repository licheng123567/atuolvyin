from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class RiskKeyword(Base, TimestampMixin):
    __tablename__ = "risk_keyword"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    speaker: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    level: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    keyword: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "category", "keyword", name="uq_risk_keyword_tenant_cat_kw"),
    )
