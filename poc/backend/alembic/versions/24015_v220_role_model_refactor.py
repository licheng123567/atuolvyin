"""v2.2 — 角色模型重构:platform_role / work_mode / 删 source_type / CHECK 约束

Revision ID: 24015v220
Revises: 24014v210
Create Date: 2026-05-16 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24015v220"
down_revision: str | None = "24014v210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_CK = "ck_user_tenant_membership_role"
_PLATFORM_CK = "ck_user_account_platform_role"
_WORK_MODE_CK = "ck_user_tenant_membership_work_mode"


def upgrade() -> None:
    # 1. 加新列(先可空,回填后再加约束)
    op.add_column("user_account", sa.Column("platform_role", sa.String(16), nullable=True))
    op.add_column(
        "user_tenant_membership", sa.Column("work_mode", sa.String(16), nullable=True)
    )

    # 2. 回填 work_mode(必须在 role 改值之前 —— 依赖旧 agent_* 值)
    op.execute(
        "UPDATE user_tenant_membership SET work_mode='internal' WHERE role='agent_internal'"
    )
    op.execute(
        "UPDATE user_tenant_membership SET work_mode='external' WHERE role='agent_external'"
    )

    # 3. 回填 platform_role(从平台 membership 推),然后删除这些平台 membership 行
    op.execute(
        """
        UPDATE user_account SET platform_role='ops' WHERE id IN (
            SELECT user_id FROM user_tenant_membership WHERE role='platform_ops'
        )
        """
    )
    op.execute(
        """
        UPDATE user_account SET platform_role='superadmin' WHERE id IN (
            SELECT user_id FROM user_tenant_membership
            WHERE role IN ('platform_superadmin','platform_super')
        )
        """
    )
    op.execute(
        "DELETE FROM user_tenant_membership "
        "WHERE role IN ('platform_ops','platform_superadmin','platform_super')"
    )
    # 无任何 membership 的账号 → 一次性判定为 superadmin
    op.execute(
        """
        UPDATE user_account SET platform_role='superadmin'
        WHERE platform_role IS NULL
          AND id NOT IN (SELECT DISTINCT user_id FROM user_tenant_membership)
        """
    )

    # 4. 收敛 role(顺序无关 —— 每条 UPDATE 命中互斥的旧值集合)
    op.execute("UPDATE user_tenant_membership SET role='admin' WHERE role='provider_admin'")
    op.execute("UPDATE user_tenant_membership SET role='agent' WHERE role IN ('agent_internal','agent_external')")
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager' "
        "WHERE role IN ('project_manager_property','project_manager_provider',"
        "'property_manager_property','property_manager_provider')"
    )

    # 5. 删冗余列 source_type
    op.drop_column("user_tenant_membership", "source_type")

    # 6. 加 CHECK 约束
    op.create_check_constraint(
        _ROLE_CK,
        "user_tenant_membership",
        "role IN ('admin','project_manager','supervisor','agent','legal','coordinator')",
    )
    op.create_check_constraint(
        _PLATFORM_CK,
        "user_account",
        "platform_role IS NULL OR platform_role IN ('superadmin','ops')",
    )
    op.create_check_constraint(
        _WORK_MODE_CK,
        "user_tenant_membership",
        "(role = 'agent') = (work_mode IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_WORK_MODE_CK, "user_tenant_membership", type_="check")
    op.drop_constraint(_PLATFORM_CK, "user_account", type_="check")
    op.drop_constraint(_ROLE_CK, "user_tenant_membership", type_="check")

    # 重建 source_type,按 provider_id 回填
    op.add_column(
        "user_tenant_membership",
        sa.Column("source_type", sa.Text(), nullable=False, server_default="INTERNAL"),
    )
    op.execute(
        "UPDATE user_tenant_membership SET source_type='PROVIDER' WHERE provider_id IS NOT NULL"
    )
    op.alter_column("user_tenant_membership", "source_type", server_default=None)

    # role 反映射(注意:provider_admin/agent_internal 等区分信息靠 provider_id/work_mode)
    op.execute(
        "UPDATE user_tenant_membership SET role='provider_admin' "
        "WHERE role='admin' AND provider_id IS NOT NULL"
    )
    op.execute("UPDATE user_tenant_membership SET role='agent_internal' WHERE work_mode='internal'")
    op.execute("UPDATE user_tenant_membership SET role='agent_external' WHERE work_mode='external'")
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager_provider' "
        "WHERE role='project_manager' AND provider_id IS NOT NULL"
    )
    op.execute(
        "UPDATE user_tenant_membership SET role='project_manager_property' "
        "WHERE role='project_manager' AND provider_id IS NULL"
    )

    # 平台账号还原一条 membership 不可靠(原 tenant_id 已丢失)—— downgrade 仅恢复列结构,
    # 平台角色还原需重跑 seed。删列即可。
    op.drop_column("user_tenant_membership", "work_mode")
    op.drop_column("user_account", "platform_role")
