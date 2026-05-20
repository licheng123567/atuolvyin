"""Sprint 16.1 — 法务转化通道 (PRD §20.4)。

把"催收无果 → 一键转法务追诉"做成独立收入线：

- LegalServicePackage：4 种服务包目录（律师函/诉前调解/小额诉讼/完整代理）
- LegalConversionOrder：物业公司从 CRM 案件下单 → 平台撮合律所 → 接单完成
  含催收时间线摘要 + 推荐处理方式 + 预估成本/回款概率（创建时冻结）
"""

from __future__ import annotations

from datetime import date, datetime
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
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending")
    price_quoted: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    platform_fee_amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
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
    # v1.9.0 — 物业内部法务处理环节字段
    internal_close_reason: Mapped[str | None] = mapped_column(sa.String(32))
    internal_closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    internal_closed_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    # v1.9.1 — closed_promised 时记业主承诺缴清日期，到期未付列表显示红标 + 可重新打开
    promise_due_date: Mapped[date | None] = mapped_column(sa.Date)

    __table_args__ = (
        sa.CheckConstraint(
            # v1.9.0 — 加 internal_processing + 4 closed_* + escalated_to_lawfirm
            "status IN ('pending','dispatched','in_service','completed','cancelled',"
            "'internal_processing','closed_paid','closed_promised',"
            "'closed_uncollectible','escalated_to_lawfirm')",
            name="ck_legal_conv_status",
        ),
        sa.CheckConstraint(
            "internal_close_reason IS NULL OR internal_close_reason IN "
            "('paid','promised','uncollectible','escalated')",
            name="ck_legal_conv_close_reason",
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
    # v0.5.4 — 申请理由改 NOT NULL（前端必填，预设原因 + 可选补充）
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # v0.5.4 — status 列加宽到 32 (原 20 不够装 "approved_pending_legal")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending")
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
    # v0.5.4 — 督导手动「上报 admin」时间戳
    escalated_to_admin_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True)
    )

    __table_args__ = (
        # v0.5.4 — status 加 pending_admin（督导上报后）+ approved_pending_legal（已批待法务接单选包，Stream 3）
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled',"
            "'pending_admin','approved_pending_legal')",
            name="ck_legal_conv_req_status",
        ),
        sa.Index("ix_legal_conv_req_tenant_status", "tenant_id", "status"),
        sa.Index("ix_legal_conv_req_case", "case_id"),
    )


class LegalConversionRequestMaterial(Base, TimestampMixin):
    """§9.1 — 服务商法务为某「法务转化请求」上传的补充材料附件。

    归属经 request → case → project.provider_id 推导，故不设 provider_id 列。
    """

    __tablename__ = "legal_conversion_request_material"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_conversion_request.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(sa.Text)
    size_bytes: Mapped[int | None] = mapped_column(sa.Integer)
    uploaded_by: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("ix_legal_conv_req_material_request", "request_id"),
        sa.Index("ix_legal_conv_req_material_tenant", "tenant_id"),
    )
