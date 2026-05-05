import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.storage import storage
from app.workers.pipeline import process_call

router = APIRouter()


@router.post("/upload")
def upload_recording(
    background: BackgroundTasks,
    task_id: int = Form(...),
    device_id: str = Form(...),
    callee_phone: str = Form(...),
    started_at: str = Form(...),       # ISO8601
    ended_at: str = Form(...),
    duration_sec: int = Form(...),
    src_path: str = Form(""),
    match_method: str = Form("name_match"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    dev = db.execute(text("SELECT id, agent_phone FROM device WHERE device_id=:d"),
                     {"d": device_id}).fetchone()
    if not dev:
        raise HTTPException(404, "device not registered")
    dev_pk, caller_phone = dev[0], dev[1]

    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))

    cl_id = db.execute(text("""
        INSERT INTO call_log(task_id, device_id, caller_phone, callee_phone,
                             started_at, ended_at, duration_sec,
                             status, recording_match_status)
        VALUES (:tid, :did, :caller, :callee, :s, :e, :dur, 'uploaded', 'matched')
        RETURNING id
    """), dict(tid=task_id, did=dev_pk, caller=caller_phone, callee=callee_phone,
               s=started, e=ended, dur=duration_sec)).scalar()

    raw = file.file.read()
    fmt = (file.filename or "").rsplit(".", 1)[-1].lower() or "bin"
    object_key = f"calls/{cl_id}/{uuid.uuid4().hex}.{fmt}"
    storage.put_object(object_key, raw, file.content_type or "audio/mpeg")
    pub = storage.get_url(object_key)

    db.execute(text("""
        INSERT INTO recording_file(call_log_id, object_key, public_url,
                                   src_path, size_bytes, duration_sec, format, match_method)
        VALUES (:cid, :ok, :url, :sp, :sz, :dur, :fmt, :mm)
    """), dict(cid=cl_id, ok=object_key, url=pub, sp=src_path,
               sz=len(raw), dur=duration_sec, fmt=fmt, mm=match_method))

    db.execute(text("UPDATE task SET status='in_progress' WHERE id=:t"), {"t": task_id})
    db.commit()

    background.add_task(process_call, cl_id)
    return {"call_log_id": cl_id, "recording_url": pub}


@router.post("/{call_id}/business")
def submit_business(call_id: int, payload: dict, db: Session = Depends(get_db)):
    """坐席通话结束后提交的业务表单（投票勾选 / 催收承诺等）"""
    cl = db.execute(text("SELECT task_id FROM call_log WHERE id=:c"), {"c": call_id}).fetchone()
    if not cl:
        raise HTTPException(404, "call not found")
    task_id = cl[0]
    t = db.execute(text("SELECT type, owner_id, payload FROM task WHERE id=:t"),
                   {"t": task_id}).mappings().fetchone()
    if not t:
        raise HTTPException(404, "task not found")

    if t["type"] == "vote":
        db.execute(text("""
            INSERT INTO vote_record(owner_id, motion_id, choice, source, evidence_call_id, note)
            VALUES (:o, :m, :c, 'call', :cid, :n)
            ON CONFLICT (owner_id, motion_id) DO UPDATE
              SET choice=EXCLUDED.choice, evidence_call_id=EXCLUDED.evidence_call_id,
                  note=EXCLUDED.note
        """), dict(o=t["owner_id"], m=t["payload"]["motion_id"],
                   c=payload.get("choice", "未明确"), cid=call_id,
                   n=payload.get("note")))
    elif t["type"] == "collection":
        db.execute(text("""
            INSERT INTO collection_promise(owner_id, amount, promise_date,
                                           excuse_category, evidence_call_id, note)
            VALUES (:o, :a, :d, :ec, :cid, :n)
        """), dict(o=t["owner_id"],
                   a=payload.get("amount") or t["payload"].get("amount"),
                   d=payload.get("promise_date"),
                   ec=payload.get("excuse_category"),
                   cid=call_id, n=payload.get("note")))

    db.execute(text("UPDATE task SET status='done' WHERE id=:t"), {"t": task_id})
    db.commit()
    return {"ok": True}


@router.get("/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT cl.*, rf.public_url AS recording_url,
               tr.full_text, tr.segments, tr.asr_model,
               ex.fields AS extraction_fields, ex.needs_review, ex.llm_model
        FROM call_log cl
        LEFT JOIN recording_file rf ON rf.call_log_id=cl.id
        LEFT JOIN transcript tr ON tr.call_log_id=cl.id
        LEFT JOIN extraction ex ON ex.call_log_id=cl.id
        WHERE cl.id=:c
    """), {"c": call_id}).mappings().fetchone()
    if not row:
        raise HTTPException(404, "not found")
    return dict(row)
