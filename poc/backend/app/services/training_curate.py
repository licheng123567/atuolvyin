"""v0.6.0 — 培训案例自动入库 + 入库辅助。

两条入库路径:
1. 从风险事件 → 培训:当督导处置某 RiskEvent 时选了
   `handle_status='transferred_training'`,本服务的 `from_risk_event()` 自动
   创建一条 TrainingCase(category='escalate',source='auto')。被
   `app/api/supervisor_extras.py` 的 PATCH 端点调用。
2. 督导手工录入:走 `from_manual()`,POST /supervisor/training-cases。

定时任务:`scan_auto_ingest_loop()` 由 main.py lifespan 启动,每 24h 跑一次,
扫近 7 天「已设 handle_status='transferred_training' 但 raw_risk_event_id
还没建训练案例」的事件,自动补建(防止督导处置时联动失败的兜底)。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.call import CallRecord, RiskEvent
from app.models.training_case import TrainingCase

logger = logging.getLogger(__name__)


def from_risk_event(
    db: Session,
    *,
    risk_event_id: int,
    tenant_id: int,
    actor_user_id: int | None = None,
) -> TrainingCase | None:
    """从一条已处置的风险事件生成培训案例。

    幂等:若同一 raw_risk_event_id 已有 training_case 则直接返回它。
    """
    # 已存在?
    existing = db.execute(
        select(TrainingCase)
        .where(
            TrainingCase.raw_risk_event_id == risk_event_id,
            TrainingCase.tenant_id == tenant_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        return None

    call = db.get(CallRecord, event.call_id)
    if call is None or call.tenant_id != tenant_id:
        return None

    # 自动文案 — 基于 trigger_text + disposition_note(督导处理结果)生成
    title = f"风险事件复盘:{(event.trigger_text or event.category)[:40]}"
    scenario_parts = [
        f"事件级别:{event.level}",
        f"触发类别:{event.category}",
    ]
    if event.trigger_text:
        scenario_parts.append(f"触发文本:{event.trigger_text}")
    scenario = "\n".join(scenario_parts)
    lesson = event.disposition_note or "(督导未填写处理结果 — 自动入库时建议补充)"

    tc = TrainingCase(
        tenant_id=tenant_id,
        title=title,
        category="escalate",  # 风险事件转入 → 升级处置
        scenario=scenario,
        lesson=lesson,
        raw_call_id=event.call_id,
        raw_risk_event_id=risk_event_id,
        source="auto",
        created_by=actor_user_id,
        rating=3,  # 默认中等 — 督导可后续编辑
    )
    db.add(tc)
    db.flush()
    return tc


# ── 兜底循环:扫近 7 天「漏建」的事件 ──────────────────────────────
SCAN_INTERVAL_SEC = 24 * 3600  # 每 24h 跑一次
LOOKBACK_DAYS = 7


def scan_and_ingest_missed(db: Session) -> int:
    """扫近 7 天 handle_status='transferred_training' 但还没有
    training_case 的 risk_event,自动补建。返回新建数。
    """
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)

    # 查需要补建的 event_id 列表
    rows = db.execute(
        select(RiskEvent.id, CallRecord.tenant_id, RiskEvent.disposition_by)
        .join(CallRecord, CallRecord.id == RiskEvent.call_id)
        .where(RiskEvent.handle_status == "transferred_training")
        .where(RiskEvent.disposition_at >= cutoff)
        .outerjoin(TrainingCase, TrainingCase.raw_risk_event_id == RiskEvent.id)
        .where(TrainingCase.id.is_(None))
    ).all()

    count = 0
    for event_id, tenant_id, actor_id in rows:
        try:
            tc = from_risk_event(
                db,
                risk_event_id=int(event_id),
                tenant_id=int(tenant_id),
                actor_user_id=int(actor_id) if actor_id else None,
            )
            if tc is not None:
                count += 1
        except Exception:
            logger.exception("from_risk_event failed for event %s, skipped", event_id)
    if count:
        db.commit()
    return count


async def scan_auto_ingest_loop() -> None:
    """无限循环 — FastAPI lifespan 中 create_task 启动。"""
    logger.info(
        "training_curate.scan_auto_ingest_loop started (interval=%ds)",
        SCAN_INTERVAL_SEC,
    )
    while True:
        try:
            with SessionLocal() as db:
                created = scan_and_ingest_missed(db)
                if created:
                    logger.info("training_curate: auto-ingested %d new training cases", created)
        except Exception as exc:
            logger.exception("scan_auto_ingest_loop iteration failed: %s", exc)
        await asyncio.sleep(SCAN_INTERVAL_SEC)
