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
    CallTagOut,
    CallTagPatch,
    CallUploadResponse,
    DialRequestIn,
    DialRequestOut,
    SuggestionFeedbackIn,
    TranscriptOut,
    TranscriptSegment,
)
from app.services import mipush
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


@router.post("/dial-request", response_model=DialRequestOut, status_code=201)
async def dial_request(
    body: DialRequestIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DialRequestOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == body.case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于当前租户"},
        )
    if case.assigned_to != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "案件未分配给当前催收员"},
        )

    # Look up most-recent device with a push_reg_id
    device = db.execute(
        select(DeviceProfile)
        .where(
            DeviceProfile.user_id == user_id,
            DeviceProfile.tenant_id == tenant_id,
            DeviceProfile.push_reg_id.isnot(None),
        )
        .order_by(DeviceProfile.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_PUSH_NOT_REGISTERED", "message": "设备未注册推送，请重新登录催收 App"},
        )

    # Resolve owner info for the DIAL_REQUEST payload
    from app.models.case import OwnerProfile  # local import to avoid potential cycles
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    owner_name = owner.name if owner else "未知业主"
    owner_phone_masked = mask_phone(owner.phone_enc) if owner and owner.phone_enc else ""

    # Insert pending_dial CallRecord
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case.id,
        caller_user_id=user_id,
        callee_phone_enc=owner.phone_enc if owner and owner.phone_enc else "",
        initiated_by="pc",
        status="pending_dial",
    )
    db.add(call)
    db.flush()

    # Send MiPush
    push_client = mipush.get_mipush_client()
    payload_dict = {
        "type": "DIAL_REQUEST",
        "call_id": call.id,
        "case_id": case.id,
        "owner_name": owner_name,
        "owner_phone_masked": owner_phone_masked,
    }
    try:
        await push_client.send_to_user(
            reg_id=device.push_reg_id,
            payload=payload_dict,
            title="新外呼任务",
            description=f"{owner_name} · {owner_phone_masked}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_PUSH_FAILED", "message": "推送失败，请稍后重试"},
        ) from exc

    db.commit()
    return DialRequestOut(call_id=call.id, status="dispatched")


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


@router.patch("/{call_id}/tag", response_model=CallTagOut)
def patch_call_tag(
    call_id: int,
    body: CallTagPatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CallTagOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)

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
    if call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权修改此通话"},
        )

    analysis = db.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == call_id)
    ).scalar_one_or_none()
    if not analysis:
        analysis = AnalysisResult(call_id=call_id, key_segments={})
        db.add(analysis)
        db.flush()

    # Merge into key_segments (don't overwrite existing fields with None)
    seg = dict(analysis.key_segments or {})
    if body.intent is not None:
        seg["intent"] = body.intent
    if body.promise_date is not None:
        seg["promise_date"] = body.promise_date
    if body.promise_amount is not None:
        seg["promise_amount"] = body.promise_amount
    analysis.key_segments = seg
    if body.notes is not None:
        analysis.summary = body.notes

    call.user_confirmed_at = datetime.now(timezone.utc)
    db.commit()

    # 推断业务信号
    if body.intent:
        from app.services.signal_inference import infer_signals_for_call
        infer_signals_for_call(call.id, body.intent, db)
        db.commit()

    db.refresh(analysis)
    db.refresh(call)

    return CallTagOut(
        call_id=call.id,
        intent=seg.get("intent"),
        promise_date=seg.get("promise_date"),
        promise_amount=seg.get("promise_amount"),
        summary=analysis.summary,
        user_confirmed_at=call.user_confirmed_at,
    )


@router.post("/{call_id}/suggestions/{suggestion_id}/feedback", status_code=201)
def post_suggestion_feedback(
    call_id: int,
    suggestion_id: str,
    body: SuggestionFeedbackIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    from fastapi.responses import JSONResponse
    from app.models.call import SuggestionFeedback

    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id, CallRecord.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )
    if call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权对此通话提交反馈"},
        )

    if body.action not in ("adopt", "ignore"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "action 必须是 adopt 或 ignore"},
        )

    existing = db.execute(
        select(SuggestionFeedback).where(
            SuggestionFeedback.call_id == call_id,
            SuggestionFeedback.suggestion_id == suggestion_id,
        )
    ).scalar_one_or_none()
    if existing:
        # idempotent — return 200 without re-inserting
        return JSONResponse(status_code=200, content={})

    fb = SuggestionFeedback(
        call_id=call_id,
        suggestion_id=suggestion_id,
        user_id=user_id,
        action=body.action,
        suggestion_text=body.suggestion_text or "",
        script_template_id=body.script_template_id,
    )
    db.add(fb)
    db.flush()

    # 采用时累计 usage_count
    if body.action == "adopt" and body.script_template_id is not None:
        from app.models.script import ScriptTemplate
        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ScriptTemplate)
            .where(ScriptTemplate.id == body.script_template_id)
            .values(usage_count=ScriptTemplate.usage_count + 1)
        )

    db.commit()
    return {"id": fb.id}
