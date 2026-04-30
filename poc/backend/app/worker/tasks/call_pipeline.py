from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app

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
        try:
            session.close()
        finally:
            pass  # engine is module-level, not disposed per-call


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    """Sprint 3a: mark call as queued. Sprint 3b: ASR → LLM → Transcript + AnalysisResult."""
    from app.models.call import CallRecord

    with _get_db() as db:
        call = db.get(CallRecord, call_id)
        if not call:
            return
        call.status = "queued"
        # 不在这里 commit，由 _get_db context manager 统一管理
