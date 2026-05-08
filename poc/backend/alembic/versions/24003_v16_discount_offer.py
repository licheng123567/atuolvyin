"""v1.6 — DiscountOffer 表（协商打折 / 减免审批）

Revision ID: 24003v16
Revises: 24002v16
Create Date: 2026-05-09 09:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = '24003v16'
down_revision: str | None = '24002v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discount_offer",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.BigInteger(),
            sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "applicant_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applicant_role", sa.String(16), nullable=False),
        sa.Column("offer_type", sa.String(32), nullable=False),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("proposed_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_pct", sa.SmallInteger(), nullable=False),
        sa.Column("installment_months", sa.SmallInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="pending_supervisor",
        ),
        sa.Column("approver_role_required", sa.String(16), nullable=False),
        sa.Column(
            "approved_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "audit_trail",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
    )
    op.create_index("ix_discount_offer_tenant_id", "discount_offer", ["tenant_id"])
    op.create_index("ix_discount_offer_case_id", "discount_offer", ["case_id"])
    op.create_index("ix_discount_offer_status", "discount_offer", ["status"])
    op.create_index(
        "ix_discount_offer_tenant_status",
        "discount_offer",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_discount_offer_tenant_status", table_name="discount_offer")
    op.drop_index("ix_discount_offer_status", table_name="discount_offer")
    op.drop_index("ix_discount_offer_case_id", table_name="discount_offer")
    op.drop_index("ix_discount_offer_tenant_id", table_name="discount_offer")
    op.drop_table("discount_offer")
