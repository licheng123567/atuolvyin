"""v1.0.0 — AuditLog 加 provider_id(服务商 scope 审计)

诱因:用户反馈服务商应有自己的审计日志。AuditLog 原仅有 tenant_id,
无法直接按服务商过滤。本期加 provider_id 字段(nullable);
服务商相关路由调用 log_audit 时传 provider_id;
查询时按 provider_id == self_provider 过滤。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "24102v100c"
down_revision: str | None = "24101v100b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column(
            "provider_id",
            sa.BigInteger(),
            sa.ForeignKey("service_provider.id"),
            nullable=True,
        ),
    )
    op.create_index("idx_audit_log_provider_created", "audit_log", ["provider_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_log_provider_created", "audit_log")
    op.drop_column("audit_log", "provider_id")
