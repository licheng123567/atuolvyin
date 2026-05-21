"""v0.6.0 — 话术 AI 评分算法 + asyncio 循环(FastAPI lifespan 启动)。

scan_and_recompute_ai_scores(db) — 每日凌晨跑一次,或 admin POST 手动触发。
recompute_ai_scores_loop() — main.py 的 lifespan 调,sleep 1h 扫一次「现在该不该重算」。

算法:
  1. 时间窗:近 30 天的 SuggestionFeedback 记录(action='adopt'/'ignore' 都计入推送次数,
     仅 adopt 计入采用次数)
  2. 关联:SuggestionFeedback.script_template_id → call_record.id
                                              → call_record.case_id → collection_case
  3. 回款率 recovery_rate = adopted_calls_with_paid_case / total_adopted_calls
     - 「采用过该话术且案件已 stage=paid 的通话数」/「采用过该话术的通话数」
  4. 采用率 adoption_rate = adopted / total_shown(本算法内重算,不依赖 ScriptTemplate
     的已有字段 — 因为旧字段口径不一)
  5. ai_score = (recovery_rate × 70 + adoption_rate × 30) × 1.0,clip 到 [0,100]
  6. sample_count = total_shown(用于 UI 判定「样本不足」)

样本量保护:
  - sample_count < 5 时:写 ai_score = NULL(不展示)
  - sample_count 5-9 时:正常算 ai_score,但 UI 应显示「样本不足」徽章
  - sample_count >= 10 时:正常展示

设计权衡:
  - 没有独立 PaymentRecord 表 — 用 case.stage='paid' 作为回款判定(与现有 effectiveness
    API 同口径,见 admin_scripts.py)
  - 加权 70/30 反映 PRD §20.1 的核心 KPI(回款是终极指标,采用是过程指标)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.call import CallRecord, SuggestionFeedback
from app.models.case import CollectionCase
from app.models.script import ScriptTemplate

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 30
WEIGHT_RECOVERY = 70  # 回款率权重
WEIGHT_ADOPTION = 30  # 采用率权重
MIN_SAMPLE_FOR_SCORE = 5  # 样本数 <5 不算分


class ScriptScoreResult(NamedTuple):
    """单条话术的重算结果(供日志 / 测试用)。"""

    script_template_id: int
    sample_count: int
    adoption_rate: float | None
    recovery_rate: float | None
    ai_score: Decimal | None


def recompute_one(
    db: Session, script_template_id: int, *, lookback_days: int = LOOKBACK_DAYS
) -> ScriptScoreResult:
    """重算单条话术的 AI 评分。

    供单测 + 手动触发(POST /admin/scripts/{id}/recompute-ai-score)用。
    """
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    # 一次查询:total_shown / total_adopted / total_adopted_with_paid_case
    row = db.execute(
        select(
            func.count(SuggestionFeedback.id).label("total_shown"),
            func.sum(case((SuggestionFeedback.action == "adopt", 1), else_=0)).label(
                "total_adopted"
            ),
            func.sum(
                case(
                    (
                        (SuggestionFeedback.action == "adopt") & (CollectionCase.stage == "paid"),
                        1,
                    ),
                    else_=0,
                )
            ).label("total_adopted_paid"),
        )
        .select_from(SuggestionFeedback)
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .outerjoin(CollectionCase, CollectionCase.id == CallRecord.case_id)
        .where(SuggestionFeedback.script_template_id == script_template_id)
        .where(SuggestionFeedback.created_at >= cutoff)
    ).one()

    total_shown = int(row.total_shown or 0)
    total_adopted = int(row.total_adopted or 0)
    total_adopted_paid = int(row.total_adopted_paid or 0)

    adoption_rate: float | None = None
    recovery_rate: float | None = None
    ai_score: Decimal | None = None

    if total_shown >= MIN_SAMPLE_FOR_SCORE:
        adoption_rate = (total_adopted / total_shown) if total_shown > 0 else 0.0
        recovery_rate = (total_adopted_paid / total_adopted) if total_adopted > 0 else 0.0
        raw = recovery_rate * WEIGHT_RECOVERY + adoption_rate * WEIGHT_ADOPTION
        ai_score = Decimal(f"{max(0.0, min(100.0, raw)):.2f}")

    template = db.get(ScriptTemplate, script_template_id)
    if template is not None:
        template.ai_score = ai_score
        template.ai_score_sample_count = total_shown
        template.ai_score_updated_at = datetime.now(UTC)
        db.flush()

    return ScriptScoreResult(
        script_template_id=script_template_id,
        sample_count=total_shown,
        adoption_rate=adoption_rate,
        recovery_rate=recovery_rate,
        ai_score=ai_score,
    )


def scan_and_recompute_ai_scores(
    db: Session, *, lookback_days: int = LOOKBACK_DAYS, tenant_id: int | None = None
) -> int:
    """扫描所有 active 话术 + 重算 ai_score,返回处理条数。

    定时任务每天凌晨调一次;tenant_id 可选 — 限制本次只处理某租户(用于 OPS 调试)。
    调用方负责 db.commit()。
    """
    stmt = select(ScriptTemplate.id).where(ScriptTemplate.is_active.is_(True))
    if tenant_id is not None:
        stmt = stmt.where(ScriptTemplate.tenant_id == tenant_id)

    ids = db.execute(stmt).scalars().all()
    count = 0
    for sid in ids:
        try:
            recompute_one(db, int(sid), lookback_days=lookback_days)
            count += 1
        except Exception:
            logger.exception("recompute_one failed for script_template %s, skipped", sid)
    logger.info("script_ai_score: recomputed %d / %d templates", count, len(ids))
    return count


# ── asyncio loop:lifespan 启动,每 6h 扫一次「是否需要重算」 ──────────
RECOMPUTE_INTERVAL_SEC = 6 * 3600  # 6 小时
STALE_THRESHOLD_HOURS = 24  # 上次重算超过 24h 视为过期,触发重算


async def recompute_ai_scores_loop() -> None:
    """无限循环 — FastAPI lifespan 中 create_task 启动。

    每 6h 检查一次:若任意 active 话术的 ai_score_updated_at 超过 24h
    (或为 NULL),触发全量重算。避免短时间内重复跑(每次重算成本不低)。
    """
    logger.info(
        "recompute_ai_scores_loop started (interval=%ds, stale=%dh)",
        RECOMPUTE_INTERVAL_SEC,
        STALE_THRESHOLD_HOURS,
    )
    while True:
        try:
            with SessionLocal() as db:
                # 检查最旧的 ai_score_updated_at
                stale_cutoff = datetime.now(UTC) - timedelta(hours=STALE_THRESHOLD_HOURS)
                row = db.execute(
                    select(func.min(ScriptTemplate.ai_score_updated_at)).where(
                        ScriptTemplate.is_active.is_(True)
                    )
                ).scalar_one_or_none()

                if row is None or row < stale_cutoff:
                    count = scan_and_recompute_ai_scores(db)
                    db.commit()
                    logger.info(
                        "recompute_ai_scores_loop: recomputed %d templates",
                        count,
                    )
                else:
                    logger.debug(
                        "recompute_ai_scores_loop: skip — oldest update %s is fresh",
                        row,
                    )
        except Exception as exc:
            logger.exception("recompute_ai_scores_loop iteration failed: %s", exc)
        await asyncio.sleep(RECOMPUTE_INTERVAL_SEC)
