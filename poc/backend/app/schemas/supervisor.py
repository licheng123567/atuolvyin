"""Sprint 9.4 / 9.5 — supervisor view schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# v0.6.0 — 风险事件处理状态枚举(与 RiskEvent.handle_status 列 CHECK 约束一致)
RiskEventHandleStatus = Literal[
    "resolved", "escalated", "transferred_training", "transferred_legal"
]


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
    disposition_note: str | None  # supervisor's manual annotation(作为处理结果)
    disposition_at: datetime | None
    agent_user_id: int | None
    agent_name: str | None
    handle_status: RiskEventHandleStatus | None = None  # v0.6.0


class RiskEventNoteIn(BaseModel):
    """督导处置弹窗提交体。

    v0.6.0:扩展为 (note, handle_status) — note 保留为「处理结果」文本,
    handle_status 标记处置类型(resolved / escalated / transferred_training / transferred_legal)。
    """

    note: str
    handle_status: RiskEventHandleStatus | None = None  # v0.6.0


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
