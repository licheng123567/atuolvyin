"""Sprint 16.1 — 法务转化通道 (PRD §20.4)。

把"催收无果 → 一键转法务追诉"做成独立收入线：

- LegalServicePackage：4 种服务包目录（律师函/诉前调解/小额诉讼/完整代理）
- LegalConversionOrder：物业公司从 CRM 案件下单 → 平台撮合律所 → 接单完成
  含催收时间线摘要 + 推荐处理方式 + 预估成本/回款概率（创建时冻结）
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LegalServicePackage(Base, TimestampMixin):
    """4 种法务服务包配置。平台级（tenant_id 为 NULL = 全局）+ 租户可定制。"""

    __tablename__ = "legal_service_package"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    package_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    platform_fee_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 4), nullable=False, default=Decimal("0.25")
    )
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    __table_args__ = (
        sa.CheckConstraint(
            "package_type IN ('lawyer_letter','mediation','small_claims','full_agency')",
            name="ck_legal_pkg_type",
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_legal_pkg_tenant_slug"),
    )


class LegalConversionOrder(Base, TimestampMixin):
    """法务转化订单：CRM 案件 → 服务包 → 律所撮合 → 完结。"""

    __tablename__ = "legal_conversion_order"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_service_package.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="pending"
    )
    price_quoted: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    platform_fee_amount: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False
    )
    law_firm_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("law_firm.id", ondelete="SET NULL")
    )
    lawyer_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("law_firm_lawyer.id", ondelete="SET NULL")
    )
    assigned_law_firm: Mapped[str | None] = mapped_column(sa.String(200))
    assigned_lawyer_name: Mapped[str | None] = mapped_column(sa.String(120))
    timeline_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost_estimate: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending','dispatched','in_service','completed','cancelled')",
            name="ck_legal_conv_status",
        ),
        sa.Index("ix_legal_conv_tenant_status", "tenant_id", "status"),
    )


class LegalConversionRequest(Base, TimestampMixin):
    """v1.6.8 — 法务转化申请：催收员提申请 → 督导/admin 审批 → 创建 Order。

    与 LegalConversionOrder 的区别：
    - Request 在审批前；Order 在审批通过后（或 admin 直接建单）
    - 申请阶段不选服务包，由审批人决定 package_id
    """

    __tablename__ = "legal_conversion_request"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requester_role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="pending"
    )
    reviewer_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    reviewer_role: Mapped[str | None] = mapped_column(sa.String(32))
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(sa.Text)
    related_order_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_conversion_order.id", ondelete="SET NULL"),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="ck_legal_conv_req_status",
        ),
        sa.Index("ix_legal_conv_req_tenant_status", "tenant_id", "status"),
        sa.Index("ix_legal_conv_req_case", "case_id"),
    )
