from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReviewItemOut(BaseModel):
    """督导复核列表项"""

    model_config = ConfigDict(from_attributes=True)

    call_id: int
    case_id: int | None = None
    callee_phone_masked: str
    started_at: datetime | None = None
    duration_sec: int | None = None
    ai_intent: str | None = None
    ai_summary: str | None = None
    needs_review: bool
    supervisor_quality: Literal["good", "bad", "needs_improvement"] | None = None
    supervisor_review_note: str | None = None
    supervisor_reviewed_at: datetime | None = None


class ReviewLabelIn(BaseModel):
    """督导打标 input"""

    quality: Literal["good", "bad", "needs_improvement"]
    note: str | None = None
    # 可选：覆盖 AI 标签
    intent_correction: str | None = None


# Sprint 12.2 — review detail with playback context


class TranscriptSegmentOut(BaseModel):
    speaker: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    text: str | None = None


class ReviewRiskEventOut(BaseModel):
    id: int
    level: str
    category: str
    intervention: str
    trigger_text: str | None = None
    audio_offset_ms: int | None = None  # for player jump
    occurred_at: datetime


class ReviewDetailOut(ReviewItemOut):
    """单通详情：含录音 URL + 转写 + 风控事件时间点（用于播放跳转）。"""

    recording_url: str | None = None
    transcript_text: str | None = None
    transcript_segments: list[TranscriptSegmentOut] = []
    risk_events: list[ReviewRiskEventOut] = []
    asr_model: str | None = None
