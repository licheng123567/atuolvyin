# poc/backend/app/api/calls_v1.py
from __future__ import annotations

import hashlib
import logging
import math
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone, encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.core.storage import storage
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.device import DeviceProfile
from app.models.dial_token import DialToken
from app.models.settings import TenantSettings
from app.models.tenant import Tenant, TenantMinuteUsage
from app.models.user import UserAccount
from app.schemas.call import (
    AnalysisResultOut,
    CallDetailResponse,
    CallListItem,
    CallTagOut,
    CallTagPatch,
    CallUploadResponse,
    DialInfoOut,
    DialRequestIn,
    DialRequestOut,
    DialStartIn,
    DialStartOut,
    HeartbeatOut,
    LiveCallItem,
    LiveCallsOut,
    SuggestionFeedbackIn,
    TakeoverResponseIn,
    TakeoverResponseOut,
    TranscriptOut,
    TranscriptSegment,
)
from app.schemas.common import PaginatedResponse
from app.services import mipush
from app.services.audit import log_audit

QR_TOKEN_TTL_MIN = 10

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
    if body.mode not in ("push", "qr"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "mode 必须是 push 或 qr"},
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

    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    owner_name = owner.name if owner else "未知业主"
    owner_phone_masked = mask_phone(owner.phone_enc) if owner and owner.phone_enc else ""

    # Insert pending_dial CallRecord (shared by push & qr paths)
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

    # ── QR backup mode: skip MiPush, hand back deeplink + token ──
    if body.mode == "qr":
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(minutes=QR_TOKEN_TTL_MIN)
        dt = DialToken(
            call_id=call.id,
            tenant_id=tenant_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(dt)
        log_audit(
            db,
            actor_user_id=user_id,
            actor_role=payload.get("role"),
            tenant_id=tenant_id,
            action="qr_dial.requested",
            target_type="call_record",
            target_id=call.id,
            payload={"case_id": case.id},
        )
        db.commit()
        return DialRequestOut(
            call_id=call.id,
            status="qr_pending",
            qr_payload=f"autoluyin://dial?call_id={call.id}&token={token}",
            expires_at=expires_at,
        )

    # ── Default push mode: requires registered MiPush device ──
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


# ── Sprint 14.2 — App 端发起拨号同步 (PRD §10.1 / §11.6) ────────

# 软配额阈值：剩余低于此值才拒绝（避免半路砍断通话）
SOFT_QUOTA_MIN_REMAINING = 3
# 实时模式 auto 决议时所需的 realtime 余量阈值
AUTO_LIVE_THRESHOLD_MIN = 10


def _resolve_recording_mode(
    db: Session, tenant_id: int, year_month: str, settings_mode: str | None
) -> str:
    """决议本次通话的 recording_mode。冻结到 CallRecord 后不再受 TenantSettings 影响。

    规则：
    - settings_mode 显式 live/post → 直接使用
    - settings_mode 'auto' 或缺省 → 看 realtime 余量：
        余量 ≥ AUTO_LIVE_THRESHOLD_MIN → live；否则 post
    """
    mode = (settings_mode or "auto").lower()
    if mode == "live":
        return "live"
    if mode == "post":
        return "post"
    # auto
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()
    realtime_used = usage.realtime_minutes if usage else 0
    tenant = db.get(Tenant, tenant_id)
    realtime_quota: int | None = tenant.monthly_minute_quota if tenant else None
    if realtime_quota is None:
        return "live"  # 无限套餐 → 默认走 live
    return "live" if (realtime_quota - realtime_used) >= AUTO_LIVE_THRESHOLD_MIN else "post"


def _check_soft_quota(
    db: Session, tenant_id: int, year_month: str, mode: str
) -> tuple[bool, int]:
    """软配额检查：余量 ≥ SOFT_QUOTA_MIN_REMAINING 才放行。返回 (is_ok, remaining_minutes)."""
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.monthly_minute_quota is None:
        return True, 99999
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()
    used = usage.used_minutes if usage else 0
    remaining = tenant.monthly_minute_quota - used
    return remaining >= SOFT_QUOTA_MIN_REMAINING, max(0, remaining)


async def _broadcast_call_event(
    db: Session, call: CallRecord, event_type: str
) -> None:
    """向 supervisor 房间推 call.started / call.ended / call.aborted 事件。"""
    from app.risk.supervisor_manager import get_supervisor_manager

    caller = db.get(UserAccount, call.caller_user_id) if call.caller_user_id else None
    case = db.get(CollectionCase, call.case_id) if call.case_id else None
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
    payload = {
        "type": event_type,  # "call.started" | "call.ended" | "call.aborted"
        "call_id": call.id,
        "case_id": call.case_id,
        "caller_user_id": call.caller_user_id,
        "caller_name": caller.name if caller else None,
        "owner_name": owner.name if owner else None,
        "owner_phone_masked": mask_phone(owner.phone_enc) if owner and owner.phone_enc else None,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "recording_mode": call.recording_mode,
        "status": call.status,
    }
    sup = get_supervisor_manager()
    await sup.broadcast(call.tenant_id, payload)


@router.post("/dial-start", response_model=DialStartOut, status_code=201)
async def dial_start(
    body: DialStartIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DialStartOut:
    """Agent App 内点「拨打」时调用。冻结 recording_mode + 检查软配额 + WS 推送 supervisor。

    并发保护：DB 部分唯一索引 uq_active_call_per_caller 防同一 caller 双开（409）。
    Heartbeat：客户端拿到 call_id 后必须每 30s POST /calls/{id}/heartbeat，
    后台任务 90s 无心跳 → status='aborted'。
    """
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    # 1. 案件归属
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == body.case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于当前租户"},
        )
    if case.assigned_to != user_id and not (
        case.pool_type == "public" and case.assigned_to is None
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "案件未分配给当前催收员"},
        )

    # 2. 决议 recording_mode（冻结）
    year_month = datetime.now(UTC).strftime("%Y-%m")
    settings = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    mode = _resolve_recording_mode(
        db, tenant_id, year_month, settings.recording_mode if settings else None
    )

    # 3. 软配额检查
    ok, remaining = _check_soft_quota(db, tenant_id, year_month, mode)
    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_QUOTA_EXHAUSTED",
                "message": f"本月通话分钟剩余 {remaining} 分钟，低于 {SOFT_QUOTA_MIN_REMAINING} 分钟阈值，无法发起新通话",
            },
        )

    # 4. 拿 owner phone（写 callee_phone_enc）
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    callee_enc = owner.phone_enc if owner and owner.phone_enc else ""

    # 5. 插入 CallRecord(status='dialing')
    #    并发保护由 DB partial unique index 触发：同一 caller_user_id 已有
    #    status IN ('dialing','live') 的记录时插入失败 → 409
    now = datetime.now(UTC)
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case.id,
        caller_user_id=user_id,
        callee_phone_enc=callee_enc,
        initiated_by="app",
        status="dialing",
        recording_mode=mode,
        started_at=now,
        last_heartbeat_at=now,
    )
    db.add(call)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_ACTIVE_CALL_EXISTS",
                "message": "您当前已有一通进行中的通话，不能并发拨号",
            },
        ) from exc

    db.commit()
    db.refresh(call)

    # 6. WS 广播 supervisor / admin / project_manager_property
    try:
        await _broadcast_call_event(db, call, "call.started")
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.warning("broadcast call.started failed: %s", exc)

    return DialStartOut(call_id=call.id, recording_mode=mode, status="dialing")


@router.post("/{call_id}/heartbeat", response_model=HeartbeatOut)
async def call_heartbeat(
    call_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> HeartbeatOut:
    """agent App 30s 一次心跳，证明通话还在进行。后台任务 90s 无心跳自动 abort。"""
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
            CallRecord.caller_user_id == user_id,
        )
    ).scalar_one_or_none()
    if call is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话不存在或不属于当前坐席"},
        )
    if call.status not in ("dialing", "live"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_CALL_NOT_ACTIVE", "message": f"通话状态 {call.status} 不接受心跳"},
        )

    call.last_heartbeat_at = datetime.now(UTC)
    db.commit()
    db.refresh(call)
    return HeartbeatOut(call_id=call.id, status=call.status, last_heartbeat_at=call.last_heartbeat_at)


# ── Sprint 15.3 — agent 响应督导转接请求 (PRD §11.2) ────────


@router.post("/{call_id}/takeover-response", response_model=TakeoverResponseOut)
async def respond_takeover(
    call_id: int,
    body: TakeoverResponseIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TakeoverResponseOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
            CallRecord.caller_user_id == user_id,
        )
    ).scalar_one_or_none()
    if call is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话不存在或不属于当前坐席"},
        )

    from app.services.call_intervention import dispatch_takeover_response
    await dispatch_takeover_response(
        db,
        call_id=call.id,
        tenant_id=tenant_id,
        agent_user_id=user_id,
        accepted=body.accepted,
        note=body.note,
    )
    return TakeoverResponseOut(call_id=call.id, accepted=body.accepted)


@router.get("/{call_id}/dial-info", response_model=DialInfoOut)
def get_dial_info(
    call_id: int,
    token: Annotated[str, Query(min_length=10, max_length=128)],
    db: Annotated[Session, Depends(get_db)],
) -> DialInfoOut:
    """Sprint 12 — 坐席 App 扫码后调用，凭一次性 token 拿到案件信息。

    注意：本端点**不需要 JWT**，token 本身就是凭证。但 token 仅 10 分钟有效、
    单次消费、且与 call_id 严格绑定。无认证简化了扫码流程（App 可能尚未登录
    或 token 已过期 session），代价是 token 必须当作 bearer 处理。
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Atomic claim — first writer wins, prevents replay
    now = datetime.now(UTC)
    result = db.execute(
        sa_update(DialToken)
        .where(DialToken.token_hash == token_hash)
        .where(DialToken.call_id == call_id)
        .where(DialToken.used_at.is_(None))
        .where(DialToken.expires_at > now)
        .values(used_at=now)
        .returning(DialToken.id, DialToken.tenant_id)
    ).first()
    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ERR_INVALID_DIAL_TOKEN",
                "message": "二维码无效、已过期或已被使用",
            },
        )

    tenant_id_from_token = int(result.tenant_id)

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id_from_token,
        )
    ).scalar_one_or_none()
    if call is None or call.case_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话或案件不存在"},
        )

    case = db.get(CollectionCase, call.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case else None
    if not case or not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件或业主信息缺失"},
        )

    address_parts = [p for p in (owner.building, owner.room) if p]
    address = " ".join(address_parts) if address_parts else None

    log_audit(
        db,
        actor_user_id=call.caller_user_id,
        actor_role="agent",
        tenant_id=tenant_id_from_token,
        action="qr_dial.consumed",
        target_type="call_record",
        target_id=call.id,
        payload={"case_id": case.id},
    )
    db.commit()

    return DialInfoOut(
        call_id=call.id,
        case_id=case.id,
        owner_name=owner.name,
        owner_phone_masked=mask_phone(owner.phone_enc),
        owner_phone=decrypt_phone(owner.phone_enc),
        address=address,
        debt_amount=float(case.amount_owed) if case.amount_owed else None,
        months_overdue=case.months_overdue,
    )


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
    year_month = datetime.now(UTC).strftime("%Y-%m")
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
        ) from None

    # 7. Insert CallRecord — upload path = post mode (Sprint 14.1 / PRD §20.1.1)
    # 实时模式的 CallRecord 由 dial-start 提前创建，本端点只处理事后上传
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
        recording_mode="post",
    )
    db.add(call)
    db.flush()

    # 8. Update quota usage — 同时累计 used_minutes（兼容总量）和 post_minutes
    if tenant and tenant.monthly_minute_quota is not None:
        usage = _get_or_create_usage(db, tenant_id, year_month)
        minutes = math.ceil(duration_sec / 60)
        usage.used_minutes += minutes
        usage.post_minutes += minutes

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
    case_id: int | None = Query(None),
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

    transcript_out: TranscriptOut | None = None
    analysis_out: AnalysisResultOut | None = None

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

    call.user_confirmed_at = datetime.now(UTC)
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
