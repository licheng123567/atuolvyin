"""v0.5.4 — 审批模型重塑 + 转法务流程数据层

- DiscountOffer 加 escalated_to_admin_at(督导手动「上报 admin」时间戳)
- LegalConversionRequest:
    * reason 改 NOT NULL(已有 NULL 行回填占位)
    * 加 escalated_to_admin_at
    * status CHECK 扩展加 'pending_admin' + 'approved_pending_legal'

Revision ID: 24023v054a
Revises: 24022v220h
Create Date: 2026-05-19 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24023v054a"
down_revision: str | None = "24022v220h"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. DiscountOffer 加 escalated_to_admin_at
    op.add_column(
        "discount_offer",
        sa.Column(
            "escalated_to_admin_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 2. LegalConversionRequest 加 escalated_to_admin_at
    op.add_column(
        "legal_conversion_request",
        sa.Column(
            "escalated_to_admin_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 3. LegalConversionRequest.reason NULL 回填后改 NOT NULL
    op.execute(
        "UPDATE legal_conversion_request SET reason = '(历史数据未填写)' "
        "WHERE reason IS NULL"
    )
    op.alter_column(
        "legal_conversion_request",
        "reason",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 4. LegalConversionRequest.status CHECK 扩展
    op.drop_constraint(
        "ck_legal_conv_req_status",
        "legal_conversion_request",
        type_="check",
    )
    op.create_check_constraint(
        "ck_legal_conv_req_status",
        "legal_conversion_request",
        "status IN ('pending','approved','rejected','cancelled',"
        "'pending_admin','approved_pending_legal')",
    )


def downgrade() -> None:
    # 反向操作:CHECK → reason NOT NULL → 两表 escalated_to_admin_at 列

    # 4. status CHECK 收窄回原
    op.drop_constraint(
        "ck_legal_conv_req_status",
        "legal_conversion_request",
        type_="check",
    )
    op.create_check_constraint(
        "ck_legal_conv_req_status",
        "legal_conversion_request",
        "status IN ('pending','approved','rejected','cancelled')",
    )

    # 3. reason 改回 nullable
    op.alter_column(
        "legal_conversion_request",
        "reason",
        existing_type=sa.Text(),
        nullable=True,
    )

    # 2. 删 escalated_to_admin_at (legal_conversion_request)
    op.drop_column("legal_conversion_request", "escalated_to_admin_at")

    # 1. 删 escalated_to_admin_at (discount_offer)
    op.drop_column("discount_offer", "escalated_to_admin_at")
