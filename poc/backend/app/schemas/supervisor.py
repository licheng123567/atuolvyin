"""Sprint 9.4 / 9.5 — supervisor view schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RiskEventTimelineItem(BaseModel):
    id: int
    call_id: int
    case_id: int | None
    level: str  # L1 / L2 / L3
    category: str
    intervention: str  # warn / interrupt / terminate
    trigger_text: str | None
    audio_offset_ms: int | None
    occurred_at: datetime
    disposition_note: str | None  # supervisor's manual annotation
    disposition_at: datetime | None
    agent_user_id: int | None
    agent_name: str | None


class RiskEventNoteIn(BaseModel):
    note: str


class TeamPerformanceItem(BaseModel):
    user_id: int
    name: str
    total_calls: int
    connected_calls: int
    promised_cases: int
    paid_cases: int
    conversion_rate: float | None
    delta_vs_previous: float | None  # change vs previous period (-1.0 .. +inf)


class TeamPerformanceOut(BaseModel):
    period_days: int
    items: list[TeamPerformanceItem]
