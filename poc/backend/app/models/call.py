from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CallRecord(Base, TimestampMixin):
    __tablename__ = "call_record"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    case_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("collection_case.id")
    )
    caller_user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    callee_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)
    initiated_by: Mapped[str] = mapped_column(sa.Text, nullable=False, default="app")  # app / pc
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(sa.Integer)
    billable_duration: Mapped[int | None] = mapped_column(sa.Integer)  # 接通后时长（秒）
    result_tag: Mapped[str | None] = mapped_column(sa.Text)
    emotion_tag: Mapped[str | None] = mapped_column(sa.Text)
    risk_flagged: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    recording_url: Mapped[str | None] = mapped_column(sa.Text)
    object_key: Mapped[str | None] = mapped_column(sa.Text)
    data_hash: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="pending")
    user_confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.Index("idx_callrecord_tenant", "tenant_id"),
        sa.Index("idx_callrecord_case", "case_id"),
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcript"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False
    )
    full_text: Mapped[str | None] = mapped_column(sa.Text)
    segments: Mapped[dict | None] = mapped_column(sa.JSON)  # [{speaker, start_ms, end_ms, text}]
    asr_model: Mapped[str | None] = mapped_column(sa.Text)
    data_hash: Mapped[str | None] = mapped_column(sa.Text)


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_result"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(sa.Text)
    key_segments: Mapped[dict | None] = mapped_column(sa.JSON)
    followup_suggestion: Mapped[str | None] = mapped_column(sa.Text)
    prompt_version: Mapped[str | None] = mapped_column(sa.Text)
    llm_model: Mapped[str | None] = mapped_column(sa.Text)
    needs_review: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    # Sprint 8 T1 — supervisor quality review fields
    supervisor_quality: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    supervisor_review_note: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    supervisor_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    supervisor_reviewed_by: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )


class RiskEvent(Base, TimestampMixin):
    __tablename__ = "risk_event"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False
    )
    level: Mapped[str] = mapped_column(sa.Text, nullable=False)  # L1 / L2 / L3
    category: Mapped[str] = mapped_column(sa.Text, nullable=False)
    trigger_text: Mapped[str | None] = mapped_column(sa.Text)
    audio_offset_ms: Mapped[int | None] = mapped_column(sa.Integer)
    intervention: Mapped[str] = mapped_column(sa.Text, nullable=False)  # warn / interrupt / terminate
    data_hash: Mapped[str | None] = mapped_column(sa.Text)
    # Sprint 9.4 — supervisor manual disposition annotation
    disposition_note: Mapped[str | None] = mapped_column(sa.Text)
    disposition_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )
    disposition_at: Mapped["datetime | None"] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class SuggestionFeedback(Base):
    __tablename__ = "suggestion_feedback"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False
    )
    suggestion_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # adopt | ignore
    suggestion_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    supervisor_label: Mapped[Optional[str]] = mapped_column(sa.String(16))  # good | bad
    supervisor_note: Mapped[Optional[str]] = mapped_column(sa.Text)
    supervisor_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=True
    )
    supervisor_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    inferred_signal: Mapped[Optional[int]] = mapped_column(sa.SmallInteger)
    script_template_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("script_template.id"), nullable=True
    )

    __table_args__ = (
        sa.UniqueConstraint("call_id", "suggestion_id", name="uq_suggestion_feedback_call_sid"),
        sa.Index("ix_suggestion_feedback_call_id", "call_id"),
    )
