# poc/backend/app/api/calls_v1.py
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.core.storage import storage
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase
from app.models.device import DeviceProfile
from app.models.tenant import Tenant, TenantMinuteUsage
from app.schemas.call import (
    AnalysisResultOut,
    CallDetailResponse,
    CallListItem,
    CallUploadResponse,
    TranscriptOut,
    TranscriptSegment,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")
SUPERVISOR_ROLES = ("supervisor", "admin")
ALLOWED_AUDIO_FORMATS = {"mp3", "m4a", "amr", "wav", "aac", "ogg"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _get_or_create_usage(db: Session, tenant_id: int, year_month: str) -> TenantMinuteUsage:
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()
    if not usage:
        try:
            usage = TenantMinuteUsage(
                tenant_id=tenant_id,
                year_month=year_month,
                used_minutes=0,
            )
            db.add(usage)
            db.flush()
        except IntegrityError:
            db.rollback()
            usage = db.execute(
                select(TenantMinuteUsage).where(
                    TenantMinuteUsage.tenant_id == tenant_id,
                    TenantMinuteUsage.year_month == year_month,
                )
            ).scalar_one()
    return usage


@router.post("/upload", response_model=CallUploadResponse, status_code=201)
async def upload_call(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    device_id: Annotated[str, Form()],
    case_id: Annotated[int, Form()],
    callee_phone: Annotated[str, Form()],
    started_at: Annotated[str, Form()],
    ended_at: Annotated[str, Form()],
    duration_sec: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
) -> CallUploadResponse:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    # 1. Verify device belongs to current user and tenant
    device = db.execute(
        select(DeviceProfile).where(
            DeviceProfile.device_id == device_id,
            DeviceProfile.user_id == user_id,
            DeviceProfile.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_DEVICE_NOT_FOUND", "message": "设备未注册或不属于当前用户"},
        )

    # 2. Verify case belongs to tenant
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于当前租户"},
        )

    # 3. Validate file format
    filename = file.filename or "recording"
    fmt = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if fmt not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_FORMAT", "message": f"不支持的音频格式: {fmt}"},
        )

    # 4. Quota check
    tenant = db.get(Tenant, tenant_id)
    year_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if tenant and tenant.monthly_minute_quota is not None:
        usage = _get_or_create_usage(db, tenant_id, year_month)
        needed = math.ceil(duration_sec / 60)
        if usage.used_minutes + needed > tenant.monthly_minute_quota:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"code": "ERR_QUOTA_EXCEEDED", "message": "本月通话分钟配额已用尽"},
            )

    # 5. Upload file to storage
    try:
        raw = await file.read()
        object_key = f"calls/{tenant_id}/{uuid.uuid4().hex}.{fmt}"
        storage.put_object(object_key, raw, file.content_type or f"audio/{fmt}")
        recording_url = storage.get_url(object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "录音上传失败，请重试"},
        ) from exc

    # 6. Encrypt callee phone and parse datetimes
    callee_phone_enc = encrypt_phone(callee_phone)
    try:
        started_dt = datetime.fromisoformat(started_at)
        ended_dt = datetime.fromisoformat(ended_at)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "无效的时间格式，使用 ISO8601"},
        )

    # 7. Insert CallRecord
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case_id,
        caller_user_id=user_id,
        callee_phone_enc=callee_phone_enc,
        initiated_by="app",
        started_at=started_dt,
        ended_at=ended_dt,
        duration_sec=duration_sec,
        recording_url=recording_url,
        object_key=object_key,
        status="uploaded",
    )
    db.add(call)
    db.flush()

    # 8. Update quota usage
    if tenant and tenant.monthly_minute_quota is not None:
        usage = _get_or_create_usage(db, tenant_id, year_month)
        usage.used_minutes += math.ceil(duration_sec / 60)

    db.commit()
    db.refresh(call)

    # 9. Dispatch async processing task (CELERY_TASK_ALWAYS_EAGER=True in tests)
    from app.worker.tasks.call_pipeline import process_call
    process_call.delay(call.id)

    return CallUploadResponse(call_id=call.id, status="uploaded")


@router.get("/", response_model=PaginatedResponse[CallListItem])
def list_calls(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES, *SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    case_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CallListItem]:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    role: str = payload.get("role", "")

    stmt = select(CallRecord).where(CallRecord.tenant_id == tenant_id)
    if role in AGENT_ROLES:
        stmt = stmt.where(CallRecord.caller_user_id == user_id)
    if case_id:
        stmt = stmt.where(CallRecord.case_id == case_id)

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    calls = (
        db.execute(
            stmt.order_by(CallRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    items = [
        CallListItem(
            id=c.id,
            case_id=c.case_id,
            callee_phone_masked=mask_phone(c.callee_phone_enc),
            started_at=c.started_at,
            ended_at=c.ended_at,
            duration_sec=c.duration_sec,
            status=c.status,
            created_at=c.created_at,
        )
        for c in calls
    ]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{call_id}", response_model=CallDetailResponse)
def get_call_detail(
    call_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES, *SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CallDetailResponse:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    role: str = payload.get("role", "")

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if not call:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )

    if role in AGENT_ROLES and call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权访问此通话记录"},
        )

    transcript_out: Optional[TranscriptOut] = None
    analysis_out: Optional[AnalysisResultOut] = None

    if call.status == "processed":
        t = db.execute(
            select(Transcript).where(Transcript.call_id == call_id)
        ).scalar_one_or_none()
        if t:
            segs = None
            if t.segments:
                segs = [TranscriptSegment(**s) for s in t.segments]
            transcript_out = TranscriptOut(
                full_text=t.full_text or "",
                segments=segs,
                asr_model=t.asr_model,
            )

        a = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call_id)
        ).scalar_one_or_none()
        if a:
            kv = a.key_segments or {}
            analysis_out = AnalysisResultOut(
                summary=a.summary,
                intent=kv.get("intent"),
                promise_date=kv.get("promise_date"),
                excuse_category=kv.get("excuse_category"),
                compliance_disclosed=kv.get("compliance_disclosed"),
                risk_keywords=kv.get("risk_keywords"),
                confidence=kv.get("confidence"),
                needs_review=a.needs_review,
            )

    return CallDetailResponse(
        id=call.id,
        case_id=call.case_id,
        callee_phone_masked=mask_phone(call.callee_phone_enc),
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_sec=call.duration_sec,
        recording_url=call.recording_url,
        status=call.status,
        transcript=transcript_out,
        analysis=analysis_out,
        created_at=call.created_at,
    )
