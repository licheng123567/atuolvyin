"""v1.6 — 协商打折 / 减免回款审批 (PRD §3.16 待补)。

物业催收常见场景：业主主张「服务质量异议」「家庭困难」「房屋空置」时，催收员/督导
谈成减免方案 → 提交审批 → 业主限期缴清。

权限矩阵（按 TenantSettings 阈值）：
- 折扣 < discount_auto_approve_threshold_pct → 系统自动批准
- 折扣 ≤ discount_supervisor_max_pct → 督导审批
- 否则 → 物业 admin 审批
- 若 TenantSettings.discount_disabled = True → 整个功能禁用

7 天有效期：批准后业主必须在 expires_at 前缴清，否则 status=expired，需重新申请。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class DiscountOffer(Base, TimestampMixin):
    __tablename__ = "discount_offer"

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
    # §9.2-A — 减免归属：NULL = 物业内勤发起；非 NULL = 服务商催收员发起，值为其服务商 id
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    applicant_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
    )
    applicant_role: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    offer_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    proposed_amount: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    discount_pct: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    installment_months: Mapped[int | None] = mapped_column(sa.SmallInteger)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(24), nullable=False, default="pending_supervisor", index=True
    )
    approver_role_required: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(sa.Text)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    audit_trail: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb")
    )

    __table_args__ = (
        sa.CheckConstraint(
            "offer_type IN ('principal_discount','late_fee_waive','installment','long_overdue_compromise')",
            name="ck_discount_offer_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending_supervisor','pending_admin','approved','rejected','executed','expired')",
            name="ck_discount_offer_status",
        ),
        sa.CheckConstraint(
            "approver_role_required IN ('supervisor','admin')",
            name="ck_discount_offer_approver_role",
        ),
        sa.CheckConstraint(
            "applicant_role IN ('agent','supervisor')",
            name="ck_discount_offer_applicant_role",
        ),
        sa.CheckConstraint(
            "discount_pct BETWEEN 0 AND 100",
            name="ck_discount_offer_pct",
        ),
        sa.Index("ix_discount_offer_tenant_status", "tenant_id", "status"),
    )
