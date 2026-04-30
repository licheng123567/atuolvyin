from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin",
    )
    engine = create_engine(url)
    SessionLocal = sessionmaker(engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    """Sprint 3a: mark call as queued. Sprint 3b: ASR → LLM → Transcript + AnalysisResult."""
    from app.models.call import CallRecord

    with _get_db() as db:
        call = db.get(CallRecord, call_id)
        if not call:
            return
        call.status = "queued"
        db.commit()
