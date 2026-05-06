"""Sprint 8 T1 — Supervisor Quality Review router.

GET  /api/v1/supervisor/reviews        — paginated list of calls needing review
PATCH /api/v1/supervisor/reviews/{call_id} — label a call with quality rating
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import AnalysisResult, CallRecord, RiskEvent, Transcript
from app.schemas.common import PaginatedResponse
from app.schemas.review import (
    ReviewDetailOut,
    ReviewItemOut,
    ReviewLabelIn,
    ReviewRiskEventOut,
    TranscriptSegmentOut,
)

router = APIRouter()

REVIEW_ROLES = ("supervisor", "admin")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "Token does not contain tenant_id"},
        )
    return int(tenant_id)


def _to_review_item(call: CallRecord, analysis: AnalysisResult) -> ReviewItemOut:
    """Convert ORM rows to ReviewItemOut."""
    callee_masked = mask_phone(call.callee_phone_enc)
    ai_intent: str | None = None
    if analysis.key_segments and isinstance(analysis.key_segments, dict):
        ai_intent = analysis.key_segments.get("intent")

    return ReviewItemOut(
        call_id=call.id,
        case_id=call.case_id,
        callee_phone_masked=callee_masked,
        started_at=call.started_at,
        duration_sec=call.duration_sec,
        ai_intent=ai_intent,
        ai_summary=analysis.summary,
        needs_review=analysis.needs_review,
        supervisor_quality=analysis.supervisor_quality,  # type: ignore[arg-type]
        supervisor_review_note=analysis.supervisor_review_note,
        supervisor_reviewed_at=analysis.supervisor_reviewed_at,
    )


@router.get("/reviews", response_model=PaginatedResponse[ReviewItemOut])
def list_reviews(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*REVIEW_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    only_pending: bool = Query(True, description="仅未复核（supervisor_quality 为空）"),
) -> PaginatedResponse[ReviewItemOut]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(CallRecord, AnalysisResult)
        .join(AnalysisResult, AnalysisResult.call_id == CallRecord.id)
        .where(
            CallRecord.tenant_id == tenant_id,
            AnalysisResult.needs_review.is_(True),
        )
    )

    if only_pending:
        stmt = stmt.where(AnalysisResult.supervisor_quality.is_(None))

    # Count
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CallRecord.started_at.desc(), CallRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_to_review_item(call, analysis) for call, analysis in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/reviews/{call_id}", response_model=ReviewItemOut)
def label_review(
    call_id: int,
    body: ReviewLabelIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*REVIEW_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewItemOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)

    # Verify call belongs to this tenant
    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if call is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )

    # Get or create AnalysisResult
    analysis = db.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == call_id)
    ).scalar_one_or_none()

    if analysis is None:
        analysis = AnalysisResult(
            call_id=call_id,
            needs_review=True,
        )
        db.add(analysis)
        db.flush()

    # Write review fields
    analysis.supervisor_quality = body.quality
    analysis.supervisor_review_note = body.note
    analysis.supervisor_reviewed_at = datetime.now(timezone.utc)
    analysis.supervisor_reviewed_by = user_id

    # Optional intent correction
    if body.intent_correction is not None:
        segments = dict(analysis.key_segments) if analysis.key_segments else {}
        segments["intent"] = body.intent_correction
        analysis.key_segments = segments

    db.commit()
    db.refresh(analysis)

    return _to_review_item(call, analysis)


@router.get("/reviews/{call_id}", response_model=ReviewDetailOut)
def get_review_detail(
    call_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*REVIEW_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ReviewDetailOut:
    """Sprint 12.2 — 单条复核详情：含录音 URL + 转写 + 风控时间点列表，
    供前端复核工作台播放器使用（点击事件可跳转到对应 audio_offset_ms）。"""
    tenant_id = _require_tenant(payload)

    row = db.execute(
        select(CallRecord, AnalysisResult)
        .join(AnalysisResult, AnalysisResult.call_id == CallRecord.id)
        .where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "复核条目不存在"},
        )
    call, analysis = row

    transcript = db.execute(
        select(Transcript).where(Transcript.call_id == call_id)
    ).scalar_one_or_none()

    risk_events = (
        db.execute(
            select(RiskEvent)
            .where(RiskEvent.call_id == call_id)
            .order_by(RiskEvent.audio_offset_ms.asc().nulls_last(), RiskEvent.id.asc())
        )
        .scalars()
        .all()
    )

    base = _to_review_item(call, analysis)

    segments_out: list[TranscriptSegmentOut] = []
    if transcript and transcript.segments:
        for seg in transcript.segments:
            if isinstance(seg, dict):
                segments_out.append(
                    TranscriptSegmentOut(
                        speaker=seg.get("speaker"),
                        start_ms=seg.get("start_ms"),
                        end_ms=seg.get("end_ms"),
                        text=seg.get("text"),
                    )
                )

    risk_out = [
        ReviewRiskEventOut(
            id=r.id,
            level=r.level,
            category=r.category,
            intervention=r.intervention,
            trigger_text=r.trigger_text,
            audio_offset_ms=r.audio_offset_ms,
            occurred_at=r.created_at,
        )
        for r in risk_events
    ]

    return ReviewDetailOut(
        **base.model_dump(),
        recording_url=call.recording_url,
        transcript_text=transcript.full_text if transcript else None,
        transcript_segments=segments_out,
        risk_events=risk_out,
        asr_model=transcript.asr_model if transcript else None,
    )
