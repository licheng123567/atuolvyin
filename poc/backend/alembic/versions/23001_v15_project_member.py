"""v1.5 S18.5 — project_member 关联表（项目团队：督导组 + 默认催收员）

Revision ID: 23001v15
Revises: 22007v14
Create Date: 2026-05-08 09:00:00.000000

语义：
- 一个项目可绑定 N 个督导（role_in_project='supervisor'）
- 一个项目可绑定 N 个默认催收员（role_in_project='agent'）
- 案件导入到该项目时按 agent 成员 round-robin 自动 assigned_to
- 督导按 project_member 过滤可见的项目 / 案件
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '23001v15'
down_revision: str | None = '22007v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_member",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id"),
            nullable=False,
        ),
        sa.Column(
            "role_in_project", sa.String(32), nullable=False
        ),  # supervisor | agent
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
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
        sa.UniqueConstraint(
            "project_id", "user_id", "role_in_project",
            name="uq_project_member_pid_uid_role",
        ),
        sa.CheckConstraint(
            "role_in_project IN ('supervisor','agent')",
            name="ck_project_member_role",
        ),
    )
    op.create_index("idx_project_member_pid", "project_member", ["project_id"])
    op.create_index("idx_project_member_uid", "project_member", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_project_member_uid", table_name="project_member")
    op.drop_index("idx_project_member_pid", table_name="project_member")
    op.drop_table("project_member")
