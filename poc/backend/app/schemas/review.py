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
