"""Sprint 8.3 — Admin reports (PRD §3.12)."""

from __future__ import annotations

from pydantic import BaseModel


class FunnelStageOut(BaseModel):
    stage: str
    label: str
    count: int


class AgentPerformanceOut(BaseModel):
    user_id: int
    name: str
    total_calls: int
    connected_calls: int
    promised_cases: int
    conversion_rate: float | None  # promised_cases / total_calls


class ObjectionItemOut(BaseModel):
    intent: str
    count: int


class PromiseFollowupOut(BaseModel):
    total_promised: int
    total_paid: int
    rate: float | None


class ReportOverviewOut(BaseModel):
    period_days: int
    funnel: list[FunnelStageOut]
    agent_performance: list[AgentPerformanceOut]
    objection_distribution: list[ObjectionItemOut]
    promise_followup: PromiseFollowupOut
