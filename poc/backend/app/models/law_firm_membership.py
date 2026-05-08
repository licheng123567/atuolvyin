"""v1.5.7 S2 — 律所成员表（PRD §20.4 法务转化通道）。

把外部律所的代表 / 律师纳入系统账号体系：
- role_in_firm='admin'：律所代表，可在律所工作台为本所订单分配律师
- role_in_firm='lawyer'：律所内律师，承办具体订单 + 上传文书 + 完结
- 一个 user_account 可在 N 个律所有成员关系（多挂靠律师），但同一律所内仅一条成员记录
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LawFirmMembership(Base, TimestampMixin):
    __tablename__ = "law_firm_membership"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    law_firm_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("law_firm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lawyer_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("law_firm_lawyer.id", ondelete="SET NULL"),
    )
    role_in_firm: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        sa.CheckConstraint(
            "role_in_firm IN ('admin', 'lawyer')",
            name="ck_law_firm_membership_role",
        ),
        sa.UniqueConstraint(
            "user_id", "law_firm_id", name="uq_law_firm_membership_user_firm"
        ),
        sa.Index("ix_law_firm_membership_firm_role", "law_firm_id", "role_in_firm"),
    )
