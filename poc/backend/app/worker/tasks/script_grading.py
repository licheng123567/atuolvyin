from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC

from sqlalchemy import Integer, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_session_factory():
    global _engine, _SessionLocal
    if _engine is None:
        url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin",
        )
        _engine = create_engine(url)
        _SessionLocal = sessionmaker(_engine)
    return _SessionLocal


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="tasks.compute_script_grades")
def compute_script_grades() -> None:
    from datetime import datetime, timedelta

    from app.models.call import SuggestionFeedback
    from app.models.script import ScriptTemplate

    cutoff = datetime.now(UTC) - timedelta(days=30)

    with _get_db() as db:
        scripts = db.execute(select(ScriptTemplate)).scalars().all()
        for script in scripts:
            stats = db.execute(
                select(
                    func.count(SuggestionFeedback.id).label("total"),
                    func.sum((SuggestionFeedback.action == "adopt").cast(Integer)).label("adopted"),
                    func.count(func.distinct(SuggestionFeedback.call_id)).label("calls"),
                    func.sum((SuggestionFeedback.inferred_signal == 1).cast(Integer)).label(
                        "positive"
                    ),
                ).where(
                    SuggestionFeedback.script_template_id == script.id,
                    SuggestionFeedback.created_at >= cutoff,
                )
            ).one()

            total = stats.total or 0
            adopted = stats.adopted or 0
            calls = stats.calls or 0
            positive = stats.positive or 0

            if total == 0:
                continue

            adoption_rate = adopted / total
            conversion_rate = positive / calls if calls > 0 else 0.0
            script.adoption_rate = adoption_rate
            script.conversion_rate = conversion_rate

            if adoption_rate >= 0.60:
                grade = "A"
            elif adoption_rate >= 0.40:
                grade = "B"
            elif adoption_rate >= 0.20:
                grade = "C"
            else:
                grade = "D"

            script.score_grade = grade

            if grade == "D" and script.usage_count >= 20 and script.is_active:
                script.is_active = False
                logger.info(
                    "script %d auto-disabled (grade=D, usage_count=%d)",
                    script.id,
                    script.usage_count,
                )
