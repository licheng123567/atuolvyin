from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class RiskKeyword(Base, TimestampMixin):
    """风控关键词。

    scope 三态:
    - 平台预置:tenant_id IS NULL AND provider_id IS NULL
    - 物业租户私有:tenant_id IS NOT NULL AND provider_id IS NULL
    - 服务商私有(v1.0.0):tenant_id IS NULL AND provider_id IS NOT NULL
    """

    __tablename__ = "risk_keyword"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    # v1.0.0 — 服务商私有关键词 scope(用户反馈:服务商需自己的风控关键词)
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("service_provider.id")
    )
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    speaker: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    level: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    keyword: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    __table_args__ = (
        # 原 unique 约束改为含 provider_id(允许相同 keyword 在物业 vs 服务商各存一份)
        sa.UniqueConstraint(
            "tenant_id",
            "provider_id",
            "category",
            "keyword",
            name="uq_risk_keyword_scope_cat_kw",
        ),
        sa.Index(
            "idx_riskkw_tenant_cat_speaker_active",
            "tenant_id",
            "category",
            "speaker",
            "is_active",
        ),
        sa.Index(
            "idx_riskkw_provider_cat_speaker_active",
            "provider_id",
            "category",
            "speaker",
            "is_active",
        ),
        # CHECK:tenant_id 和 provider_id 不能同时非 NULL(且 platform 预置时都 NULL)
        sa.CheckConstraint(
            "NOT (tenant_id IS NOT NULL AND provider_id IS NOT NULL)",
            name="ck_risk_keyword_scope_xor",
        ),
    )
