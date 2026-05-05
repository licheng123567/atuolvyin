"""5b-001 — script library tables + suggestion_feedback extensions.

Revision ID: 5b001
Revises: 4001a1b2c3d4
Create Date: 2026-05-05 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5b001"
down_revision = "4001a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_template",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("trigger_intent", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("adoption_rate", sa.Float),
        sa.Column("conversion_rate", sa.Float),
        sa.Column("score_grade", sa.String(1)),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("score_grade IN ('A','B','C','D')", name="ck_st_score_grade"),
    )
    op.create_index("idx_script_template_tenant", "script_template", ["tenant_id"])
    op.create_index("idx_script_template_active", "script_template", ["tenant_id", "is_active"])

    op.create_table(
        "script_template_version",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("script_template_id", sa.BigInteger,
                  sa.ForeignKey("script_template.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("trigger_intent", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("edited_by", sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("script_template_id", "version", name="uq_script_version"),
    )

    op.create_table(
        "tenant_suggestion_config",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger,
                  sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("sensitivity", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("max_per_push", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("sensitivity BETWEEN 1 AND 5", name="ck_tsc_sensitivity"),
        sa.CheckConstraint("max_per_push BETWEEN 1 AND 10", name="ck_tsc_max_per_push"),
    )

    op.add_column("suggestion_feedback", sa.Column("supervisor_label", sa.String(16)))
    op.add_column("suggestion_feedback", sa.Column("supervisor_note", sa.Text))
    op.add_column("suggestion_feedback", sa.Column("supervisor_id", sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True))
    op.add_column("suggestion_feedback", sa.Column("supervisor_at", sa.DateTime(timezone=True)))
    op.add_column("suggestion_feedback", sa.Column("inferred_signal", sa.SmallInteger))
    op.add_column("suggestion_feedback", sa.Column("script_template_id", sa.BigInteger, sa.ForeignKey("script_template.id"), nullable=True))


def downgrade() -> None:
    for col in ("script_template_id", "inferred_signal", "supervisor_at",
                "supervisor_id", "supervisor_note", "supervisor_label"):
        op.drop_column("suggestion_feedback", col)
    op.drop_table("tenant_suggestion_config")
    op.drop_table("script_template_version")
    op.drop_index("idx_script_template_active", "script_template")
    op.drop_index("idx_script_template_tenant", "script_template")
    op.drop_table("script_template")
