"""Sprint 8.4 — Compliance monthly report (PRD §3.13)."""
from __future__ import annotations

from pydantic import BaseModel


class RiskEventBucket(BaseModel):
    level: str  # L1 / L2 / L3
    category: str
    count: int


class ComplianceMonthlyReport(BaseModel):
    year_month: str  # YYYY-MM
    tenant_name: str
    period_start: str  # ISO date
    period_end: str  # ISO date
    total_calls: int
    total_minutes: int
    total_risk_events: int
    risk_events_by_level: dict[str, int]  # {L1: 12, L2: 5, L3: 1}
    risk_events_by_category: list[RiskEventBucket]
    do_not_call_violations: int
    after_hours_calls: int  # calls outside 09:00-21:00 local
    overfreq_violations: int  # contacted > 3 times in a month
    interrupted_calls: int  # risk_event intervention = interrupt/terminate
    generated_at: str  # ISO timestamp


class ComplianceReportListItem(BaseModel):
    year_month: str
    total_calls: int
    total_risk_events: int
    do_not_call_violations: int
