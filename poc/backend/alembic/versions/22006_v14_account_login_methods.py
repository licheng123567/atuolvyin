"""v1.4 S17.4 — 账号体系：信用代码登录入口 + OTP 验证码 + 邮箱字段

Revision ID: 22006v14
Revises: 22005v14
Create Date: 2026-05-07 18:00:00.000000

改动：
- user_account 加 email / login_method 字段
- 新表 login_otp（手机号 → 验证码 + 过期时间，登录 / 密码重置共用）
- 已存在：tenant.credit_code（unique）；service_provider 加 credit_code
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22006v14'
down_revision: str | None = '22005v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_account",
        sa.Column("email", sa.String(120), nullable=True),
    )
    op.create_unique_constraint(
        "uq_user_account_email", "user_account", ["email"]
    )
    op.add_column(
        "user_account",
        sa.Column(
            "login_method",
            sa.String(16),
            nullable=False,
            server_default="phone",
        ),
    )
    op.add_column(
        "service_provider",
        sa.Column("credit_code", sa.String(32), nullable=True),
    )
    op.create_unique_constraint(
        "uq_service_provider_credit_code",
        "service_provider",
        ["credit_code"],
    )

    op.create_table(
        "login_otp",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("phone_enc", sa.Text(), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False, default="login"),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_login_otp_phone", "login_otp", ["phone_enc", "purpose"]
    )


def downgrade() -> None:
    op.drop_index("idx_login_otp_phone", table_name="login_otp")
    op.drop_table("login_otp")
    op.drop_constraint(
        "uq_service_provider_credit_code", "service_provider", type_="unique"
    )
    op.drop_column("service_provider", "credit_code")
    op.drop_column("user_account", "login_method")
    op.drop_constraint("uq_user_account_email", "user_account", type_="unique")
    op.drop_column("user_account", "email")
