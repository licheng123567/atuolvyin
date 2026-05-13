"""v1.5 S18.5 — Project team membership (supervisor / agent)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_member"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    role_in_project: Mapped[str] = mapped_column(
        sa.String(32), nullable=False
    )  # supervisor | agent | coordinator | legal (v1.5.6 — 协调员/法务对接人按项目绑定)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            "role_in_project",
            name="uq_project_member_pid_uid_role",
        ),
        sa.CheckConstraint(
            "role_in_project IN ('supervisor','agent','coordinator','legal')",
            name="ck_project_member_role",
        ),
        sa.Index("idx_project_member_pid", "project_id"),
        sa.Index("idx_project_member_uid", "user_id"),
    )
