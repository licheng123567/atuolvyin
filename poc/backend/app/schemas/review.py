from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ReviewItemOut(BaseModel):
    """督导复核列表项"""

    model_config = ConfigDict(from_attributes=True)

    call_id: int
    case_id: Optional[int] = None
    callee_phone_masked: str
    started_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    ai_intent: Optional[str] = None
    ai_summary: Optional[str] = None
    needs_review: bool
    supervisor_quality: Optional[Literal["good", "bad", "needs_improvement"]] = None
    supervisor_review_note: Optional[str] = None
    supervisor_reviewed_at: Optional[datetime] = None


class ReviewLabelIn(BaseModel):
    """督导打标 input"""

    quality: Literal["good", "bad", "needs_improvement"]
    note: Optional[str] = None
    # 可选：覆盖 AI 标签
    intent_correction: Optional[str] = None


# Sprint 12.2 — review detail with playback context


class TranscriptSegmentOut(BaseModel):
    speaker: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    text: Optional[str] = None


class ReviewRiskEventOut(BaseModel):
    id: int
    level: str
    category: str
    intervention: str
    trigger_text: Optional[str] = None
    audio_offset_ms: Optional[int] = None  # for player jump
    occurred_at: datetime


class ReviewDetailOut(ReviewItemOut):
    """单通详情：含录音 URL + 转写 + 风控事件时间点（用于播放跳转）。"""

    recording_url: Optional[str] = None
    transcript_text: Optional[str] = None
    transcript_segments: list[TranscriptSegmentOut] = []
    risk_events: list[ReviewRiskEventOut] = []
    asr_model: Optional[str] = None
