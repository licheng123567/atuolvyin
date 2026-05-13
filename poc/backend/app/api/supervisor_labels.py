from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord, SuggestionFeedback
from app.schemas.script import SupervisorLabelCreate, SupervisorLabelOut

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin")


@router.get("/script-labels", response_model=list[SupervisorLabelOut])
def list_script_labels(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = Query(False),
) -> list[SupervisorLabelOut]:
    tenant_id = int(payload.get("tenant_id") or 0)
    stmt = (
        select(SuggestionFeedback)
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(
            CallRecord.tenant_id == tenant_id,
            SuggestionFeedback.script_template_id.is_not(None),
        )
    )
    if unread_only:
        stmt = stmt.where(SuggestionFeedback.supervisor_label.is_(None))
    stmt = stmt.order_by(CallRecord.started_at.desc()).limit(200)
    rows = db.execute(stmt).scalars().all()
    return [
        SupervisorLabelOut(
            feedback_id=r.id,
            call_id=r.call_id,
            suggestion_text=r.suggestion_text,
            supervisor_label=r.supervisor_label,
            supervisor_note=r.supervisor_note,
            script_template_id=r.script_template_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/script-labels/{feedback_id}", response_model=SupervisorLabelOut)
def label_script(
    feedback_id: int,
    body: SupervisorLabelCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SupervisorLabelOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)
    fb = db.execute(
        select(SuggestionFeedback)
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(
            SuggestionFeedback.id == feedback_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not fb:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "反馈记录不存在"},
        )

    fb.supervisor_label = body.label
    fb.supervisor_note = body.note
    fb.supervisor_id = user_id
    fb.supervisor_at = datetime.now(UTC)
    db.commit()
    db.refresh(fb)
    return SupervisorLabelOut(
        feedback_id=fb.id,
        call_id=fb.call_id,
        suggestion_text=fb.suggestion_text,
        supervisor_label=fb.supervisor_label,
        supervisor_note=fb.supervisor_note,
        script_template_id=fb.script_template_id,
        created_at=fb.created_at,
    )
