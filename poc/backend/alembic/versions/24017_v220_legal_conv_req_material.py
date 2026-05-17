"""§9.1 — 法务转化请求补充材料附件表

Revision ID: 24017v220c
Revises: 24016v220b
Create Date: 2026-05-16 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24017v220c"
down_revision: str | None = "24016v220b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legal_conversion_request_material",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"], ["legal_conversion_request.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["user_account.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_legal_conv_req_material_request",
        "legal_conversion_request_material",
        ["request_id"],
    )
    op.create_index(
        "ix_legal_conv_req_material_tenant",
        "legal_conversion_request_material",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legal_conv_req_material_tenant",
        table_name="legal_conversion_request_material",
    )
    op.drop_index(
        "ix_legal_conv_req_material_request",
        table_name="legal_conversion_request_material",
    )
    op.drop_table("legal_conversion_request_material")
