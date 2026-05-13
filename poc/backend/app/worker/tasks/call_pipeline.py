from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.storage import storage
from app.services import asr, llm
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
        try:
            session.close()
        finally:
            pass  # engine is module-level, not disposed per-call


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    from app.models.call import AnalysisResult, CallRecord, Transcript
    from app.models.case import CollectionCase

    tmp_path: str | None = None
    try:
        with _get_db() as db:
            call = db.get(CallRecord, call_id)
            if not call:
                return

            call.status = "queued"
            db.flush()

            if not call.object_key:
                call.status = "failed"
                return

            call.status = "processing"
            db.flush()

            # Download recording to temp file
            raw = storage.get_bytes(call.object_key)
            ext = call.object_key.rsplit(".", 1)[-1] if "." in call.object_key else "mp3"
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            # ASR — idempotent: skip if transcript already exists
            existing_transcript = db.execute(
                select(Transcript).where(Transcript.call_id == call_id)
            ).scalar_one_or_none()
            if existing_transcript:
                full_text = existing_transcript.full_text or ""
            else:
                asr_result = asr.transcribe(
                    audio_url=storage.get_url(call.object_key),
                    local_file_path=tmp_path,
                )
                new_transcript = Transcript(
                    call_id=call_id,
                    full_text=asr_result["full_text"],
                    segments=asr_result.get("segments"),
                    asr_model=asr_result.get("model"),
                )
                db.add(new_transcript)
                db.flush()
                full_text = asr_result["full_text"]

            # LLM — idempotent: skip if analysis already exists
            existing_analysis = db.execute(
                select(AnalysisResult).where(AnalysisResult.call_id == call_id)
            ).scalar_one_or_none()
            if not existing_analysis:
                case = db.get(CollectionCase, call.case_id) if call.case_id else None
                llm_result = llm.extract(
                    "collection",
                    {
                        "amount_owed": str(case.amount_owed or 0) if case else "0",
                        "months_overdue": str(case.months_overdue or 0) if case else "0",
                    },
                    full_text,
                )
                fields = llm_result.get("fields", {})
                summary = " · ".join(
                    p for p in [fields.get("intent"), fields.get("excuse_category")] if p
                )
                db.add(
                    AnalysisResult(
                        call_id=call_id,
                        summary=summary,
                        key_segments=fields,
                        followup_suggestion=fields.get("promise_date"),
                        prompt_version="v1",
                        llm_model=llm_result.get("model"),
                        needs_review=bool(llm_result.get("needs_review", False)),
                    )
                )
                call.result_tag = fields.get("intent")
                db.flush()

            call.status = "processed"
            # final flush before context manager commit
            db.flush()

    except Exception as exc:
        try:
            with _get_db() as err_db:
                err_call = err_db.get(CallRecord, call_id)
                if err_call:
                    err_call.status = "failed"
        except Exception as db_exc:
            logger.error("Failed to mark call %s as failed: %s", call_id, db_exc)
        raise self.retry(exc=exc) from exc

    finally:
        if tmp_path:
            with suppress(OSError):
                os.unlink(tmp_path)
