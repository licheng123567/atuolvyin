from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── WebSocket event shapes ────────────────────────────────────


class RiskEventOut(BaseModel):
    type: str = "risk.event"
    id: str
    category: str
    speaker: str
    level: str
    trigger: str        # "keyword" | "llm" | "keyword+llm"
    matched_keyword: Optional[str] = None
    llm_confidence: Optional[float] = None
    transcript_text: str
    ts_ms: int
    raised_at: datetime


class SupervisorAlertOut(BaseModel):
    type: str = "supervisor.alert"
    call_id: int
    case_id: Optional[int] = None
    agent_user_id: int
    agent_name: str
    callee_phone_masked: str
    risk: RiskEventOut


# ── Admin CRUD schemas ────────────────────────────────────────


class RiskKeywordCreate(BaseModel):
    category: str
    speaker: str
    level: str
    keyword: str
    tenant_id: Optional[int] = None     # None = platform preset; only platform_super may set


class RiskKeywordUpdate(BaseModel):
    is_active: Optional[bool] = None
    level: Optional[str] = None


class RiskKeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    category: str
    speaker: str
    level: str
    keyword: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
