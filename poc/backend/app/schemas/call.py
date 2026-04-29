from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import PaginationQuery


class CallListQuery(PaginationQuery):
    case_id: Optional[int] = None
    status: Optional[str] = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: Optional[int]
    initiated_by: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    billable_duration: Optional[int]
    result_tag: Optional[str]
    risk_flagged: bool
    status: str
    created_at: datetime


class CallMinuteQuotaStatus(BaseModel):
    tenant_id: int
    year_month: str
    used_minutes: int
    quota: Optional[int]
    remaining: Optional[int]
    pct_used: Optional[float]
    is_exhausted: bool
