"""Sprint 13 — Legal Case management for `legal` role.

GET    /api/v1/legal/cases                              list w/ q + stage filters
POST   /api/v1/legal/cases                              create from collection_case_id
GET    /api/v1/legal/cases/{id}                         detail incl. collection_case ref
PATCH  /api/v1/legal/cases/{id}                         partial update
GET    /api/v1/legal/cases/{id}/evidence-bundle         Sprint 11.5 — ZIP 存证包
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.core.storage import storage
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.platform import BlockchainConfig
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.models.work import LegalCase
from app.schemas.common import PaginatedResponse
from app.schemas.legal import (
    CollectionCaseRef,
    LegalCaseCreate,
    LegalCaseDetailOut,
    LegalCaseOut,
    LegalCasePatch,
)

router = APIRouter()

LEGAL_ROLES = ("legal", "admin")


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _legal_to_out(lc: LegalCase, owner_name: str | None, phone_enc: str | None) -> LegalCaseOut:
    return LegalCaseOut(
        id=lc.id,
        tenant_id=lc.tenant_id,
        case_id=lc.case_id,
        stage=lc.stage,
        amount_disputed=lc.amount_disputed,
        lawyer_name=lc.lawyer_name,
        law_firm=lc.law_firm,
        next_milestone=lc.next_milestone,
        notes=lc.notes,
        created_at=lc.created_at,
        updated_at=lc.updated_at,
        owner_name=owner_name,
        owner_phone_masked=mask_phone(phone_enc) if phone_enc else None,
    )


@router.get("/cases", response_model=PaginatedResponse[LegalCaseOut])
async def list_legal_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    stage: str | None = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalCaseOut]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(LegalCase, OwnerProfile.name, OwnerProfile.phone_enc)
        .join(CollectionCase, CollectionCase.id == LegalCase.case_id)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(LegalCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(LegalCase.stage == stage)
    if q:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{q}%"))

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = db.execute(
        stmt.order_by(LegalCase.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [_legal_to_out(lc, name, phone_enc) for lc, name, phone_enc in rows]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/cases",
    response_model=LegalCaseOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_legal_case(
    body: LegalCaseCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseOut:
    tenant_id = _require_tenant(payload)

    # Verify the source collection_case is in this tenant
    cc = db.get(CollectionCase, body.case_id)
    if cc is None or cc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_NOT_FOUND", "message": "源案件不存在"},
        )

    lc = LegalCase(
        tenant_id=tenant_id,
        case_id=body.case_id,
        stage=body.stage,
        amount_disputed=body.amount_disputed,
        notes=body.notes,
        lawyer_name=body.lawyer_name,
        law_firm=body.law_firm,
        next_milestone=body.next_milestone,
    )
    db.add(lc)
    db.commit()
    db.refresh(lc)

    owner = db.get(OwnerProfile, cc.owner_id)
    return _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
    )


@router.get("/cases/{legal_case_id}", response_model=LegalCaseDetailOut)
async def get_legal_case(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseDetailOut:
    tenant_id = _require_tenant(payload)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )

    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None

    base = _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
    )

    cc_ref: CollectionCaseRef | None = None
    if cc and owner:
        cc_ref = CollectionCaseRef(
            id=cc.id,
            stage=cc.stage,
            amount_owed=cc.amount_owed,
            months_overdue=cc.months_overdue,
            owner_name=owner.name,
            owner_phone_masked=mask_phone(owner.phone_enc),
        )

    return LegalCaseDetailOut(**base.model_dump(), collection_case=cc_ref)


@router.patch("/cases/{legal_case_id}", response_model=LegalCaseOut)
async def patch_legal_case(
    legal_case_id: int,
    body: LegalCasePatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseOut:
    tenant_id = _require_tenant(payload)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(lc, field, value)

    db.commit()
    db.refresh(lc)

    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None
    return _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
    )


# ── Sprint 11.5 — Evidence bundle ZIP download (PRD §L2135) ─────────


def _ext_from_object_key(object_key: str) -> str:
    """Recover audio extension from storage object_key like 'calls/1/abc.mp3'."""
    if "." in object_key:
        return object_key.rsplit(".", 1)[-1]
    return "bin"


def _resolve_blockchain_meta(db: Session) -> dict[str, Any]:
    cfg = db.execute(
        select(BlockchainConfig)
        .where(BlockchainConfig.is_active.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    if cfg is None:
        return {
            "provider": "unconfigured",
            "endpoint": None,
            "transaction_id": None,
            "status": "pending_chain",
        }
    return {
        "provider": cfg.provider,
        "endpoint": cfg.api_endpoint,
        "transaction_id": None,  # MVP: BlockchainConfig has no SDK integration yet
        "status": "pending_chain",
    }


@router.get("/cases/{legal_case_id}/evidence-bundle")
async def download_evidence_bundle(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )

    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None
    if not cc or not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件或业主信息缺失"},
        )

    tenant = db.get(Tenant, tenant_id)
    blockchain_meta = _resolve_blockchain_meta(db)
    generated_at = datetime.now(UTC)

    # Pull all calls for this collection_case
    calls = (
        db.execute(
            select(CallRecord)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.case_id == cc.id)
            .order_by(CallRecord.id.asc())
        )
        .scalars()
        .all()
    )

    files_index: list[dict[str, Any]] = []
    base_dir = f"case_{cc.id}"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        def _write(path: str, data: bytes) -> None:
            zf.writestr(path, data)
            files_index.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
            )

        # case_summary.json
        case_summary = {
            "owner_name": owner.name,
            "owner_phone_masked": mask_phone(owner.phone_enc),
            "address": " ".join(p for p in (owner.building, owner.room) if p) or None,
            "amount_owed": str(cc.amount_owed) if cc.amount_owed is not None else None,
            "months_overdue": cc.months_overdue,
            "case_stage": cc.stage,
            "legal_stage": lc.stage,
            "lawyer_name": lc.lawyer_name,
            "law_firm": lc.law_firm,
            "next_milestone": lc.next_milestone,
        }
        _write(
            f"{base_dir}/case_summary.json",
            json.dumps(case_summary, ensure_ascii=False, indent=2).encode("utf-8"),
        )

        # Per-call artifacts
        for call in calls:
            call_dir = f"{base_dir}/calls/call_{call.id}"

            # 1. recording bytes
            recording_sha: str | None = None
            recording_skipped = False
            recording_skip_reason: str | None = None
            if call.object_key:
                try:
                    audio = storage.get_bytes(call.object_key)
                except Exception as exc:  # noqa: BLE001 — surface as 502
                    raise HTTPException(
                        status_code=http_status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "code": "ERR_BUNDLE_IO",
                            "message": f"读取录音失败 (call_id={call.id})",
                        },
                    ) from exc
                ext = _ext_from_object_key(call.object_key)
                rec_path = f"{call_dir}/recording.{ext}"
                _write(rec_path, audio)
                recording_sha = hashlib.sha256(audio).hexdigest()
            else:
                recording_skipped = True
                recording_skip_reason = "object_key 为空，未上传录音"
                files_index.append(
                    {
                        "path": f"{call_dir}/recording",
                        "skipped": True,
                        "reason": recording_skip_reason,
                    }
                )

            # 2. transcript
            transcript = db.execute(
                select(Transcript).where(Transcript.call_id == call.id)
            ).scalar_one_or_none()
            transcript_sha: str | None = None
            if transcript and transcript.full_text:
                _write(
                    f"{call_dir}/transcript.txt",
                    transcript.full_text.encode("utf-8"),
                )
                transcript_sha = files_index[-1]["sha256"]
                if transcript.segments:
                    _write(
                        f"{call_dir}/transcript.segments.json",
                        json.dumps(
                            transcript.segments, ensure_ascii=False, indent=2
                        ).encode("utf-8"),
                    )
            else:
                files_index.append(
                    {
                        "path": f"{call_dir}/transcript.txt",
                        "skipped": True,
                        "reason": "无转写内容",
                    }
                )

            # 3. AI analysis
            analysis = db.execute(
                select(AnalysisResult).where(AnalysisResult.call_id == call.id)
            ).scalar_one_or_none()
            analysis_sha: str | None = None
            if analysis:
                analysis_payload = {
                    "summary": analysis.summary,
                    "key_segments": analysis.key_segments,
                    "needs_review": analysis.needs_review,
                }
                _write(
                    f"{call_dir}/analysis.json",
                    json.dumps(
                        analysis_payload, ensure_ascii=False, indent=2
                    ).encode("utf-8"),
                )
                analysis_sha = files_index[-1]["sha256"]
            else:
                files_index.append(
                    {
                        "path": f"{call_dir}/analysis.json",
                        "skipped": True,
                        "reason": "无 AI 分析",
                    }
                )

            # 4. attestation
            attestation = {
                "call_id": call.id,
                "tenant_id": tenant_id,
                "case_id": cc.id,
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "duration_sec": call.duration_sec,
                "recording_sha256": recording_sha,
                "recording_skipped": recording_skipped,
                "recording_skip_reason": recording_skip_reason,
                "transcript_sha256": transcript_sha,
                "analysis_sha256": analysis_sha,
                "computed_at": generated_at.isoformat(),
                "blockchain": blockchain_meta,
            }
            _write(
                f"{call_dir}/attestation.json",
                json.dumps(attestation, ensure_ascii=False, indent=2).encode("utf-8"),
            )

        # bundle_manifest.json (last so it includes all prior files)
        bundle_sha = hashlib.sha256(
            "".join(f.get("sha256") or "" for f in files_index).encode("utf-8")
        ).hexdigest()
        manifest = {
            "bundle_version": "1.0",
            "generated_at": generated_at.isoformat(),
            "generated_by_user_id": user_id or None,
            "tenant_id": tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "legal_case_id": lc.id,
            "collection_case_id": cc.id,
            "call_count": len(calls),
            "files": files_index,
            "bundle_sha256": bundle_sha,
        }
        zf.writestr(
            f"{base_dir}/bundle_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    buffer.seek(0)
    filename = (
        f"evidence_case_{cc.id}_{generated_at.strftime('%Y%m%d')}.zip"
    )
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
