"""Sprint 15 — System health & metrics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ServiceStatus = Literal["ok", "degraded", "down"]


class DBHealth(BaseModel):
    status: ServiceStatus
    latency_ms: int


class BackendHealth(BaseModel):
    status: ServiceStatus
    backend: str
    last_check_at: datetime | None = None


class WebSocketHealth(BaseModel):
    status: ServiceStatus
    connected_clients: int


class ServiceHealthOut(BaseModel):
    db: DBHealth
    asr: BackendHealth
    llm: BackendHealth
    mipush: BackendHealth
    websocket: WebSocketHealth


class ServiceMetricsOut(BaseModel):
    asr_p90_sec: float
    asr_error_rate_24h: float
    llm_avg_latency_ms: float
