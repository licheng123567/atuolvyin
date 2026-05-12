"""v1.9.0 — 法务内部处理环节：3 张新表 + LegalConversionOrder 扩展

Revision ID: 24011v190
Revises: 24010v169
Create Date: 2026-05-11 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "24011v190"
down_revision: str | None = "24010v169"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. partner_law_firm ────────────────────────────────────
    op.create_table(
        "partner_law_firm",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(120)),
        sa.Column("contact_phone_enc", sa.Text),
        sa.Column("contact_email", sa.String(200)),
        sa.Column("seal_attachment_key", sa.String(512)),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_partner_law_firm_name"),
    )
    op.create_index("ix_partner_law_firm_tenant", "partner_law_firm", ["tenant_id"])

    # ── 2. internal_legal_letter_template ──────────────────────
    op.create_table(
        "internal_legal_letter_template",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("body_md", sa.Text, nullable=False),
        sa.Column("variables", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('lawyer_letter','notice','reminder','other')",
            name="ck_internal_letter_template_category",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_internal_letter_template_name"),
    )
    op.create_index(
        "ix_internal_letter_template_tenant",
        "internal_legal_letter_template",
        ["tenant_id"],
    )

    # ── 3. legal_internal_action ───────────────────────────────
    op.create_table(
        "legal_internal_action",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_order_id",
            sa.BigInteger,
            sa.ForeignKey("legal_conversion_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.BigInteger,
            sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.BigInteger,
            sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("note", sa.Text),
        sa.Column(
            "letter_template_id",
            sa.BigInteger,
            sa.ForeignKey("internal_legal_letter_template.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "partner_law_firm_id",
            sa.BigInteger,
            sa.ForeignKey("partner_law_firm.id", ondelete="SET NULL"),
        ),
        sa.Column("attachment_key", sa.String(512)),
        sa.Column("attachment_filename", sa.String(255)),
        sa.Column("letter_variables", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "action_type IN ('contact_owner','send_lawyer_letter','send_notice',"
            "'mediation','other')",
            name="ck_legal_internal_action_type",
        ),
    )
    op.create_index(
        "ix_legal_internal_action_tenant",
        "legal_internal_action",
        ["tenant_id"],
    )
    op.create_index(
        "ix_legal_internal_action_order",
        "legal_internal_action",
        ["legal_order_id", "occurred_at"],
    )
    op.create_index(
        "ix_legal_internal_action_case",
        "legal_internal_action",
        ["case_id"],
    )

    # ── 4. LegalConversionOrder 扩展 ───────────────────────────
    op.add_column(
        "legal_conversion_order",
        sa.Column("internal_close_reason", sa.String(32)),
    )
    op.add_column(
        "legal_conversion_order",
        sa.Column("internal_closed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "legal_conversion_order",
        sa.Column(
            "internal_closed_by",
            sa.BigInteger,
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
        ),
    )

    # 替换 status CHECK 约束（加 6 个新值）
    op.drop_constraint("ck_legal_conv_status", "legal_conversion_order", type_="check")
    op.create_check_constraint(
        "ck_legal_conv_status",
        "legal_conversion_order",
        "status IN ('pending','dispatched','in_service','completed','cancelled',"
        "'internal_processing','closed_paid','closed_promised',"
        "'closed_uncollectible','escalated_to_lawfirm')",
    )
    op.create_check_constraint(
        "ck_legal_conv_close_reason",
        "legal_conversion_order",
        "internal_close_reason IS NULL OR internal_close_reason IN "
        "('paid','promised','uncollectible','escalated')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_legal_conv_close_reason", "legal_conversion_order", type_="check"
    )
    op.drop_constraint("ck_legal_conv_status", "legal_conversion_order", type_="check")
    op.create_check_constraint(
        "ck_legal_conv_status",
        "legal_conversion_order",
        "status IN ('pending','dispatched','in_service','completed','cancelled')",
    )
    op.drop_column("legal_conversion_order", "internal_closed_by")
    op.drop_column("legal_conversion_order", "internal_closed_at")
    op.drop_column("legal_conversion_order", "internal_close_reason")

    op.drop_index("ix_legal_internal_action_case", table_name="legal_internal_action")
    op.drop_index("ix_legal_internal_action_order", table_name="legal_internal_action")
    op.drop_index("ix_legal_internal_action_tenant", table_name="legal_internal_action")
    op.drop_table("legal_internal_action")

    op.drop_index(
        "ix_internal_letter_template_tenant", table_name="internal_legal_letter_template"
    )
    op.drop_table("internal_legal_letter_template")

    op.drop_index("ix_partner_law_firm_tenant", table_name="partner_law_firm")
    op.drop_table("partner_law_firm")
