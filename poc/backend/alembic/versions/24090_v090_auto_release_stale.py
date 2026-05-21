"""v0.9.0 — N 天未联系自动释放公海(配置项 + 服务商 settings 表)

诱因:用户人工验收 v0.8.0 后,提出「服务商管理员及物业管理员针对多少天没有联系的
业主自动释放到公海」需求。物业自动释放进物业公海,服务商自动释放进服务商公海。

变更:
1. tenant_settings 表加 auto_release_stale_days (SmallInteger NOT NULL DEFAULT 0)
   + CHECK (0..180)
2. 新建 provider_settings 表(provider_id 唯一,目前仅含 auto_release_stale_days +
   updated_at,后续可扩展为通用服务商配置容器)

后续 Wave C.3 定时任务读这两个表 → 扫案件 → 释放 + 审计。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "24090v090a"
down_revision: str | None = "24031v060e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. tenant_settings 加列
    op.add_column(
        "tenant_settings",
        sa.Column(
            "auto_release_stale_days",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_tenant_settings_auto_release_stale_days",
        "tenant_settings",
        "auto_release_stale_days BETWEEN 0 AND 180",
    )

    # 2. provider_settings 新表
    op.create_table(
        "provider_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "provider_id",
            sa.BigInteger(),
            sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "auto_release_stale_days",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "auto_release_stale_days BETWEEN 0 AND 180",
            name="ck_provider_settings_auto_release_stale_days",
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_settings")
    op.drop_constraint(
        "ck_tenant_settings_auto_release_stale_days",
        "tenant_settings",
        type_="check",
    )
    op.drop_column("tenant_settings", "auto_release_stale_days")
