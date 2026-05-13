"""v1.6.8 — 法务转化两步审批：催收员申请 → 督导/admin 审批

Revision ID: 24009v168
Revises: 24008v162
Create Date: 2026-05-09 09:00:00.000000

新表 legal_conversion_request：
- 催收员提申请（reason 写明为何不可能自愿缴 → 申请走法务）
- 督导/admin 在审批 inbox 看到 pending 列表 → 批准（选 package + 调用现有 convert-to-legal 创建 Order）/ 驳回（写理由）
- 状态：pending | approved | rejected | cancelled
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24009v168"
down_revision: str | None = "24008v162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legal_conversion_request",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("requester_user_id", sa.BigInteger(), nullable=False),
        sa.Column("requester_role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_role", sa.String(32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("related_order_id", sa.BigInteger(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="ck_legal_conv_req_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["collection_case.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"], ["user_account.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["user_account.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["related_order_id"],
            ["legal_conversion_order.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_legal_conv_req_tenant_status",
        "legal_conversion_request",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_legal_conv_req_case", "legal_conversion_request", ["case_id"]
    )
    op.create_index(
        "ix_legal_conversion_request_tenant_id",
        "legal_conversion_request",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legal_conversion_request_tenant_id", table_name="legal_conversion_request"
    )
    op.drop_index("ix_legal_conv_req_case", table_name="legal_conversion_request")
    op.drop_index(
        "ix_legal_conv_req_tenant_status", table_name="legal_conversion_request"
    )
    op.drop_table("legal_conversion_request")
