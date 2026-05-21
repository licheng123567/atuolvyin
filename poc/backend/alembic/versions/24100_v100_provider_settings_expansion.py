"""v1.0.0 — 服务商 settings 扩展 7 个字段

诱因:v0.9.0 加 ProviderSettings 仅含 auto_release_stale_days 1 字段,
用户人工验收反馈「服务商管理员系统配置没有信息」。本期对齐 TenantSettings
补 3 类配置:录音模式 / 联系频次 / 通知规则。

变更:
1. provider_settings 表加 7 列:
   - recording_mode (String 16, default 'auto', CHECK live/post/auto)
   - contact_freq_max (SmallInt, default 3, CHECK 1..30)
   - notify_quota_warning / notify_script_disabled /
     notify_work_order_completed / notify_case_escalated /
     notify_promise_expiring (Boolean, default true)
   - notify_channels (ARRAY String, default ['system'])
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers
revision: str = "24100v100a"
down_revision: str | None = "24090v090a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 录音模式
    op.add_column(
        "provider_settings",
        sa.Column(
            "recording_mode",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
    )
    op.create_check_constraint(
        "ck_provider_settings_recording_mode",
        "provider_settings",
        "recording_mode IN ('live','post','auto')",
    )

    # 2) 联系频次
    op.add_column(
        "provider_settings",
        sa.Column(
            "contact_freq_max",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("3"),
        ),
    )
    op.create_check_constraint(
        "ck_provider_settings_freq",
        "provider_settings",
        "contact_freq_max BETWEEN 1 AND 30",
    )

    # 3) 通知规则 5 toggle + 1 channels array
    for col in (
        "notify_quota_warning",
        "notify_script_disabled",
        "notify_work_order_completed",
        "notify_case_escalated",
        "notify_promise_expiring",
    ):
        op.add_column(
            "provider_settings",
            sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    op.add_column(
        "provider_settings",
        sa.Column(
            "notify_channels",
            ARRAY(sa.String(16)),
            nullable=False,
            server_default=sa.text("ARRAY['system']::varchar[]"),
        ),
    )


def downgrade() -> None:
    for col in (
        "notify_channels",
        "notify_promise_expiring",
        "notify_case_escalated",
        "notify_work_order_completed",
        "notify_script_disabled",
        "notify_quota_warning",
    ):
        op.drop_column("provider_settings", col)

    op.drop_constraint("ck_provider_settings_freq", "provider_settings", type_="check")
    op.drop_column("provider_settings", "contact_freq_max")

    op.drop_constraint(
        "ck_provider_settings_recording_mode", "provider_settings", type_="check"
    )
    op.drop_column("provider_settings", "recording_mode")
