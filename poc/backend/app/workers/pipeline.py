"""通话处理流水线：录音 → ASR → LLM 抽取 → 业务回写。

入口 process_call(call_log_id) 由 FastAPI BackgroundTasks 触发。
"""

import json
import logging

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.services import asr, llm

logger = logging.getLogger(__name__)


def process_call(call_log_id: int):
    db = SessionLocal()
    try:
        ctx = (
            db.execute(
                text("""
            SELECT cl.id AS call_log_id, cl.task_id,
                   rf.public_url, rf.object_key,
                   t.type AS task_type, t.payload AS task_payload
            FROM call_log cl
            JOIN recording_file rf ON rf.call_log_id=cl.id
            JOIN task t ON t.id=cl.task_id
            WHERE cl.id=:c
        """),
                {"c": call_log_id},
            )
            .mappings()
            .fetchone()
        )
        if not ctx:
            logger.error("call %s not found", call_log_id)
            return

        # 1. ASR — 优先用本地文件路径（避免依赖公网 URL）
        local_path = (
            f"{settings.local_storage_root}/{ctx['object_key']}"
            if settings.storage_backend == "local"
            else None
        )
        try:
            asr_result = asr.transcribe(
                ctx["public_url"],
                hint_task_type=ctx["task_type"],
                local_file_path=local_path,
            )
        except Exception:
            logger.exception("ASR failed for call %s", call_log_id)
            db.execute(text("UPDATE call_log SET status='failed' WHERE id=:c"), {"c": call_log_id})
            db.commit()
            return

        db.execute(
            text("""
            INSERT INTO transcript(call_log_id, full_text, segments, asr_model, asr_raw)
            VALUES (:c, :ft, :seg, :m, :raw)
        """),
            dict(
                c=call_log_id,
                ft=asr_result["full_text"],
                seg=json.dumps(asr_result["segments"], ensure_ascii=False),
                m=asr_result["model"],
                raw=json.dumps(asr_result["raw"], ensure_ascii=False),
            ),
        )
        db.execute(text("UPDATE call_log SET status='transcribed' WHERE id=:c"), {"c": call_log_id})
        db.commit()

        # 2. LLM 抽取
        try:
            extraction = llm.extract(
                task_type=ctx["task_type"],
                task_payload=ctx["task_payload"],
                transcript=asr_result["full_text"],
            )
        except Exception:
            logger.exception("LLM extraction failed for call %s", call_log_id)
            return

        db.execute(
            text("""
            INSERT INTO extraction(call_log_id, type, fields, confidence, llm_model, needs_review)
            VALUES (:c, :t, :f, :conf, :m, :nr)
        """),
            dict(
                c=call_log_id,
                t=ctx["task_type"],
                f=json.dumps(extraction["fields"], ensure_ascii=False),
                conf=extraction.get("confidence"),
                m=extraction["model"],
                nr=extraction.get("needs_review", False),
            ),
        )
        db.execute(text("UPDATE call_log SET status='extracted' WHERE id=:c"), {"c": call_log_id})
        db.commit()
        logger.info("call %s pipeline done", call_log_id)
    finally:
        db.close()
