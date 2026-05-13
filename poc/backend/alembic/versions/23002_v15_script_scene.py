"""v1.5 S18.6 — script_template.scene（话术按通话场景维度组织）

Revision ID: 23002v15
Revises: 23001v15
Create Date: 2026-05-08 10:00:00.000000

scene 枚举：
- opening              开场白
- objection_handling   异议处理（与 trigger_intent 配合，二级分类）
- promise_confirm      承诺确认
- closing              挂断收尾

现有所有话术默认 scene='objection_handling'（因 trigger_intent 全是异议类）。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '23002v15'
down_revision: str | None = '23001v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "script_template",
        sa.Column(
            "scene",
            sa.String(32),
            nullable=False,
            server_default="objection_handling",
        ),
    )
    op.create_check_constraint(
        "ck_script_template_scene",
        "script_template",
        "scene IN ('opening','objection_handling','promise_confirm','closing')",
    )
    op.create_index("idx_script_template_scene", "script_template", ["scene"])


def downgrade() -> None:
    op.drop_index("idx_script_template_scene", table_name="script_template")
    op.drop_constraint(
        "ck_script_template_scene", "script_template", type_="check"
    )
    op.drop_column("script_template", "scene")
