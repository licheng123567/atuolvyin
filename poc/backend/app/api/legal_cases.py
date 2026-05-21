"""Sprint 13 — Legal Case management for `legal` role.

GET    /api/v1/legal/cases                              list w/ q + stage filters
POST   /api/v1/legal/cases                              create from collection_case_id
GET    /api/v1/legal/cases/{id}                         detail incl. collection_case ref
PATCH  /api/v1/legal/cases/{id}                         partial update
GET    /api/v1/legal/cases/{id}/evidence-bundle         Sprint 11.5 — ZIP 存证包
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import (
    get_token_payload,
    require_tenant_roles,
)
from app.models.case import CollectionCase, OwnerProfile
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


def _legal_to_out(
    lc: LegalCase,
    owner_name: str | None,
    phone_enc: str | None,
    *,
    viewer_role: str = "",
    viewer_provider_id: int | None = None,
    contract_active: bool = False,
) -> LegalCaseOut:
    """v2.2 — owner_phone_masked 字段值动态：legal 看 stage 是否在 active 集合，
    内部物业/admin 永远明文，平台永远脱敏。
    """
    reveal = should_reveal_owner_phone(
        role=viewer_role,
        provider_id=viewer_provider_id,
        contract_active=contract_active,
        legal_case_stage=lc.stage,
    )
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
        owner_phone_masked=display_owner_phone(phone_enc, reveal=reveal),
    )


@router.get("/cases", response_model=PaginatedResponse[LegalCaseOut])
async def list_legal_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
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

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    items = [
        _legal_to_out(lc, name, phone_enc, viewer_role=role, viewer_provider_id=payload.get("provider_id"), contract_active=contract_active)
        for lc, name, phone_enc in rows
    ]
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
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
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
        viewer_role=payload.get("role", ""),
        viewer_provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
    )


@router.get("/cases/{legal_case_id}", response_model=LegalCaseDetailOut)
async def get_legal_case(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
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

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    reveal = should_reveal_owner_phone(
        role=role,
        provider_id=payload.get("provider_id"),
        contract_active=contract_active,
        legal_case_stage=lc.stage,
    )

    base = _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
        viewer_role=role,
        viewer_provider_id=payload.get("provider_id"),
        contract_active=contract_active,
    )

    cc_ref: CollectionCaseRef | None = None
    if cc and owner:
        cc_ref = CollectionCaseRef(
            id=cc.id,
            stage=cc.stage,
            amount_owed=cc.amount_owed,
            months_overdue=cc.months_overdue,
            owner_name=owner.name,
            owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal) or "",
        )

    return LegalCaseDetailOut(**base.model_dump(), collection_case=cc_ref)


@router.patch("/cases/{legal_case_id}", response_model=LegalCaseOut)
async def patch_legal_case(
    legal_case_id: int,
    body: LegalCasePatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
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
        viewer_role=payload.get("role", ""),
        viewer_provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
    )


# ── Sprint 11.5 — Evidence bundle ZIP download (PRD §L2135) ─────────


@router.get("/cases/{legal_case_id}/evidence-bundle")
async def download_evidence_bundle(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    # v1.9.5 — 复用 services/evidence_bundle.py 的统一构建器
    from app.services.evidence_bundle import build_evidence_bundle_zip

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

    reveal = should_reveal_owner_phone(
        role=payload.get("role", ""),
        provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        legal_case_stage=lc.stage,
    )
    buffer, filename = build_evidence_bundle_zip(
        db,
        tenant_id=tenant_id,
        case=cc,
        owner=owner,
        owner_phone_display=display_owner_phone(owner.phone_enc, reveal=reveal),
        case_summary_extra={
            "legal_stage": lc.stage,
            "lawyer_name": lc.lawyer_name,
            "law_firm": lc.law_firm,
            "next_milestone": lc.next_milestone,
        },
        user_id=user_id or None,
        legal_case_id=lc.id,
    )
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# v0.8.0 — 法务「打包上链」按钮(只上链不下载;幂等)
@router.post("/cases/{legal_case_id}/attest")
async def attest_case_evidence(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """法务对案件证据「批量上链」— 不打包 ZIP,仅升级强证据。

    用途:案件进入诉讼/律师函阶段时,把所有通话录音/转写/分析升为司法链强证据,
         律师函/起诉状可直接附 tx_hash。

    幂等:已 confirmed 的数据(同 call_id + data_type)跳过,不重复计费。

    返回:
      attested: 本次新上链数
      already_attested: 已上链跳过数
      failed: 失败数
      total_cost: 本次费用(¥,字符串避免浮点)
    """
    from app.services.evidence_bundle import attest_case_only

    tenant_id = _require_tenant(payload)
    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )
    cc = db.get(CollectionCase, lc.case_id)
    if not cc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )

    stats = attest_case_only(
        db,
        case=cc,
        tenant_id=tenant_id,
        legal_case_id=lc.id,
    )
    return stats


# v0.8.0 — 法务案件证据状态摘要(给前端面板展示用)
@router.get("/cases/{legal_case_id}/evidence-status")
async def get_case_evidence_status(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """返回案件证据状态摘要:
       - 4 类证据各自数量
       - 已上链(confirmed) / 待上链(pending) / 仅本地(无 attestation 行)
       - 最近一次上链时间 + chain_provider

    法务前端面板调此接口决定显示「弱证据」vs「强证据」。
    """
    from sqlalchemy import func as sa_func

    from app.models.blockchain_attestation import BlockchainAttestation
    from app.models.call import CallRecord, RiskEvent

    tenant_id = _require_tenant(payload)
    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )
    cc = db.get(CollectionCase, lc.case_id)
    if not cc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )

    # 案件下所有通话 id
    call_ids = (
        db.execute(
            select(CallRecord.id)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.case_id == cc.id)
        )
        .scalars()
        .all()
    )
    call_count = len(call_ids)

    # 转写 / 分析 count(以通话存在为前提)
    transcript_count = 0
    analysis_count = 0
    if call_ids:
        transcript_count = int(
            db.execute(
                select(sa_func.count(Transcript.id))
                .where(Transcript.call_id.in_(call_ids))
                .where(Transcript.full_text.isnot(None))
            ).scalar_one()
            or 0
        )
        analysis_count = int(
            db.execute(
                select(sa_func.count(AnalysisResult.id))
                .where(AnalysisResult.call_id.in_(call_ids))
            ).scalar_one()
            or 0
        )

    # L2 风险事件 count
    l2_count = 0
    if call_ids:
        l2_count = int(
            db.execute(
                select(sa_func.count(RiskEvent.id))
                .where(RiskEvent.call_id.in_(call_ids))
                .where(RiskEvent.level == "L2")
            ).scalar_one()
            or 0
        )

    # 各 data_type 已 confirmed 数
    confirmed_rows = db.execute(
        select(
            BlockchainAttestation.data_type,
            sa_func.count(BlockchainAttestation.id),
        )
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
        .where(BlockchainAttestation.status == "confirmed")
        .group_by(BlockchainAttestation.data_type)
    ).all() if call_ids else []
    confirmed_map = {r[0]: int(r[1]) for r in confirmed_rows}

    # 各 data_type 待上链(pending)数
    pending_rows = db.execute(
        select(
            BlockchainAttestation.data_type,
            sa_func.count(BlockchainAttestation.id),
        )
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
        .where(BlockchainAttestation.status == "pending")
        .group_by(BlockchainAttestation.data_type)
    ).all() if call_ids else []
    pending_map = {r[0]: int(r[1]) for r in pending_rows}

    # 最近一次 confirmed 上链时间 + provider
    latest = db.execute(
        select(BlockchainAttestation)
        .where(BlockchainAttestation.tenant_id == tenant_id)
        .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
        .where(BlockchainAttestation.status == "confirmed")
        .order_by(BlockchainAttestation.submitted_at.desc())
        .limit(1)
    ).scalar_one_or_none() if call_ids else None

    def _build(category: str, total: int, dtype: str) -> dict:
        confirmed = confirmed_map.get(dtype, 0)
        pending = pending_map.get(dtype, 0)
        local_only = max(0, total - confirmed - pending)
        return {
            "category": category,
            "total": total,
            "confirmed": confirmed,
            "pending": pending,
            "local_only": local_only,
        }

    return {
        "legal_case_id": legal_case_id,
        "case_id": cc.id,
        "categories": [
            _build("通话录音", call_count, "call_recording"),
            _build("转写文本", transcript_count, "transcript"),
            _build("AI 分析", analysis_count, "analysis"),
            # L2 风险事件挂在 analysis 类别下(payload_metadata.risk_event_id 区分)
            # 这里单独算一行,但 confirmed/pending 字段从 analysis 复用 — 实际是从 pending 行里筛 risk_event_id 非空的;简化:不细分
            {"category": "L2 风险事件", "total": l2_count, "confirmed": 0, "pending": 0, "local_only": l2_count},
        ],
        "latest_attestation_at": (
            latest.submitted_at.isoformat() if latest and latest.submitted_at else None
        ),
        "latest_chain_provider": latest.chain_provider if latest else None,
        "has_any_confirmed": sum(confirmed_map.values()) > 0,
        "has_any_pending": sum(pending_map.values()) > 0,
    }
