"""v0.6.0 — 培训案例库表

诱因:培训案例库前端长期是纯 mock,无后端表;Wave C 接通真实 CRUD +
自动入库流(优秀通话 / 已转培训风险事件)+ 督导手工录入入口。

变更:
1. 新建 training_case 表
2. 索引:tenant_id+created_at(列表分页)
3. CHECK 约束:category/source/rating

Revision ID: 24031v060e
Revises: 24030v060d
Create Date: 2026-05-20 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24031v060e"
down_revision: str | None = "24030v060d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_case",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("lesson", sa.Text(), nullable=False),
        sa.Column("raw_call_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_risk_event_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "source", sa.String(16), nullable=False, server_default=sa.text("'manual'")
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "rating", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "views", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
            ["tenant_id"], ["tenant.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["raw_call_id"], ["call_record.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["raw_risk_event_id"], ["risk_event.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"]),
        sa.CheckConstraint(
            "category IN ('negotiate','escalate','objection','investigate')",
            name="ck_training_case_category",
        ),
        sa.CheckConstraint(
            "source IN ('auto','manual')", name="ck_training_case_source"
        ),
        sa.CheckConstraint(
            "rating BETWEEN 0 AND 5", name="ck_training_case_rating"
        ),
    )
    op.create_index(
        "idx_training_case_tenant_created",
        "training_case",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_training_case_tenant_created", table_name="training_case")
    op.drop_table("training_case")
