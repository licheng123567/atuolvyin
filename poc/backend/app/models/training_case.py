"""v0.6.0 — 培训案例库模型(PRD §22 内部培训沉淀)。

来源(source):
- auto:定时任务从优质通话/已转培训风险事件自动入库
- manual:督导手工录入(在培训库页点「手动入库」)

关键关联:
- raw_call_id → CallRecord.id(可空,纯抽象案例无来源通话)
- raw_risk_event_id → RiskEvent.id(可空,从风险事件转入时记录原 event)

UI 字段:
- rating 1-5 ★(督导主观评分,自动入库默认 4 — 来源是优质事件)
- views(学习人数,前端记 +1)
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class TrainingCase(Base, TimestampMixin):
    __tablename__ = "training_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    # 分类:negotiate(协商成功) / escalate(升级处置) / objection(异议处理) / investigate(调查定位)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    scenario: Mapped[str] = mapped_column(sa.Text, nullable=False)  # 场景描述
    lesson: Mapped[str] = mapped_column(sa.Text, nullable=False)  # 复盘要点

    # 关联(可空)
    raw_call_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id", ondelete="SET NULL"), nullable=True
    )
    raw_risk_event_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("risk_event.id", ondelete="SET NULL"), nullable=True
    )

    # 入库来源:auto(自动 curate)/ manual(督导手工)
    source: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default="manual", default="manual"
    )

    created_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )

    rating: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default="0", default=0
    )  # 0-5 ★
    views: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0", default=0)

    created_at: Mapped[datetime]  # 由 TimestampMixin 提供
    updated_at: Mapped[datetime]

    __table_args__ = (
        sa.CheckConstraint(
            "category IN ('negotiate','escalate','objection','investigate')",
            name="ck_training_case_category",
        ),
        sa.CheckConstraint("source IN ('auto','manual')", name="ck_training_case_source"),
        sa.CheckConstraint("rating BETWEEN 0 AND 5", name="ck_training_case_rating"),
        sa.Index("idx_training_case_tenant_created", "tenant_id", "created_at"),
    )
