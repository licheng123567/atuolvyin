"""v1.6 — Project 加 收费 / 合同 字段

Revision ID: 24005v16
Revises: 24004v16
Create Date: 2026-05-09 11:00:00.000000

物业管理员创建项目时录入：
- 收费标准 (charge_rate_per_sqm 元/㎡/月)
- 收费时间约定 (charge_period: monthly/quarterly/semiannual/annual)
- 合同类型 (contract_type: preliminary_service/elected/re_elected/interim_management)
- 合同有效期 + 合同 PDF 附件 (contract_attachment_key)
- 收费备注 (如不同物业类型不同费率)
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24005v16'
down_revision: str | None = '24004v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project", sa.Column("charge_rate_per_sqm", sa.Numeric(8, 4), nullable=True))
    op.add_column("project", sa.Column("charge_period", sa.String(16), nullable=True))
    op.add_column("project", sa.Column("contract_type", sa.String(32), nullable=True))
    op.add_column("project", sa.Column("contract_start_date", sa.Date(), nullable=True))
    op.add_column("project", sa.Column("contract_end_date", sa.Date(), nullable=True))
    op.add_column("project", sa.Column("contract_attachment_key", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("charge_notes", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_project_charge_period",
        "project",
        "charge_period IS NULL OR charge_period IN ('monthly','quarterly','semiannual','annual')",
    )
    op.create_check_constraint(
        "ck_project_contract_type",
        "project",
        "contract_type IS NULL OR contract_type IN ('preliminary_service','elected','re_elected','interim_management')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_contract_type", "project", type_="check")
    op.drop_constraint("ck_project_charge_period", "project", type_="check")
    op.drop_column("project", "charge_notes")
    op.drop_column("project", "contract_attachment_key")
    op.drop_column("project", "contract_end_date")
    op.drop_column("project", "contract_start_date")
    op.drop_column("project", "contract_type")
    op.drop_column("project", "charge_period")
    op.drop_column("project", "charge_rate_per_sqm")
