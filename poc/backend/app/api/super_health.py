"""Sprint 15 — System health monitoring endpoints.

GET /api/v1/super/health/services    real DB ping + dispatcher backend status
GET /api/v1/super/health/metrics     ASR p90 / error rate / LLM latency stub

Per spec: real DB ping is mandatory; ASR/LLM/MiPush surface the configured backend
(mock vs real) via the dispatcher pattern; WebSocket connected_clients is a static
placeholder until Sprint 4 ws hub exposes a counter — UI labels these as
"本期暂用模拟数据".
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_roles
from app.models.call import CallRecord
from app.models.user import UserAccount
from app.ws.connection_manager import get_connection_manager
from app.schemas.health import (
    BackendHealth,
    DBHealth,
    ServiceHealthOut,
    ServiceMetricsOut,
    WebSocketHealth,
)

router = APIRouter()

SUPER_ROLES = ("platform_super", "platform_superadmin")


def _classify_latency(latency_ms: int) -> str:
    if latency_ms < 100:
        return "ok"
    if latency_ms <= 500:
        return "degraded"
    return "down"


def _backend_status(configured: str) -> str:
    """Mock backend always 'ok'; real backend reported as 'ok' best-effort.

    A future tick can ping the real provider; for MVP the dispatcher being
    importable is treated as healthy.
    """
    return "ok"


@router.get("/health/services", response_model=ServiceHealthOut)
async def get_service_health(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceHealthOut:
    # ── DB ping ───────────────────────────────────────────────
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = int((time.perf_counter() - started) * 1000)
        db_status = _classify_latency(latency_ms)
    except SQLAlchemyError:
        latency_ms = 9999
        db_status = "down"

    now = datetime.now(UTC)

    # ── ASR / LLM / MiPush backend status (best-effort) ───────
    asr_backend = settings.asr_backend.lower()
    llm_backend = settings.llm_backend.lower()
    mipush_backend = settings.mipush_backend.lower()

    asr = BackendHealth(
        status=_backend_status(asr_backend),  # type: ignore[arg-type]
        backend=asr_backend,
        last_check_at=now,
    )
    llm = BackendHealth(
        status=_backend_status(llm_backend),  # type: ignore[arg-type]
        backend=llm_backend,
        last_check_at=now,
    )
    mipush = BackendHealth(
        status=_backend_status(mipush_backend),  # type: ignore[arg-type]
        backend=mipush_backend,
        last_check_at=now,
    )

    # ── WebSocket: live count from in-process connection_manager ──
    # 单 worker 准确；多 worker 部署需替换为 Redis 计数器（PRD §11 已注约束）
    ws_clients = get_connection_manager().total_connections()
    websocket = WebSocketHealth(status="ok", connected_clients=ws_clients)

    return ServiceHealthOut(
        db=DBHealth(status=db_status, latency_ms=latency_ms),  # type: ignore[arg-type]
        asr=asr,
        llm=llm,
        mipush=mipush,
        websocket=websocket,
    )


@router.get("/health/metrics", response_model=ServiceMetricsOut)
async def get_service_metrics(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceMetricsOut:
    since = datetime.now(UTC) - timedelta(hours=24)

    # ── ASR p90 (PERCENTILE_CONT over duration_sec last 24h) ──
    p90_sec = 0.0
    try:
        row = db.execute(
            select(
                func.percentile_cont(0.9).within_group(
                    CallRecord.duration_sec.asc()
                )
            ).where(
                CallRecord.started_at >= since,
                CallRecord.duration_sec.is_not(None),
            )
        ).scalar()
        if row is not None:
            p90_sec = float(row)
    except SQLAlchemyError:
        p90_sec = 0.0

    # ── ASR error rate (failed / total over 24h) ──────────────
    total = db.execute(
        select(func.count(CallRecord.id)).where(
            CallRecord.started_at >= since,
        )
    ).scalar() or 0
    failed = db.execute(
        select(func.count(CallRecord.id)).where(
            CallRecord.started_at >= since,
            CallRecord.status == "failed",
        )
    ).scalar() or 0
    error_rate = round(failed / total, 4) if total > 0 else 0.0

    # ── LLM avg latency: stub 0 until per-call timing recorded ─
    llm_avg_latency_ms = 0.0

    return ServiceMetricsOut(
        asr_p90_sec=p90_sec,
        asr_error_rate_24h=error_rate,
        llm_avg_latency_ms=llm_avg_latency_ms,
    )
