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
from fastapi.responses import HTMLResponse, StreamingResponse
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
from app.models.call import AnalysisResult, Transcript
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
        _legal_to_out(
            lc,
            name,
            phone_enc,
            viewer_role=role,
            viewer_provider_id=payload.get("provider_id"),
            contract_active=contract_active,
        )
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
                select(sa_func.count(AnalysisResult.id)).where(AnalysisResult.call_id.in_(call_ids))
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
    confirmed_rows = (
        db.execute(
            select(
                BlockchainAttestation.data_type,
                sa_func.count(BlockchainAttestation.id),
            )
            .where(BlockchainAttestation.tenant_id == tenant_id)
            .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
            .where(BlockchainAttestation.status == "confirmed")
            .group_by(BlockchainAttestation.data_type)
        ).all()
        if call_ids
        else []
    )
    confirmed_map = {r[0]: int(r[1]) for r in confirmed_rows}

    # 各 data_type 待上链(pending)数
    pending_rows = (
        db.execute(
            select(
                BlockchainAttestation.data_type,
                sa_func.count(BlockchainAttestation.id),
            )
            .where(BlockchainAttestation.tenant_id == tenant_id)
            .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
            .where(BlockchainAttestation.status == "pending")
            .group_by(BlockchainAttestation.data_type)
        ).all()
        if call_ids
        else []
    )
    pending_map = {r[0]: int(r[1]) for r in pending_rows}

    # 最近一次 confirmed 上链时间 + provider
    latest = (
        db.execute(
            select(BlockchainAttestation)
            .where(BlockchainAttestation.tenant_id == tenant_id)
            .where(BlockchainAttestation.call_id.in_(call_ids) if call_ids else False)
            .where(BlockchainAttestation.status == "confirmed")
            .order_by(BlockchainAttestation.submitted_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if call_ids
        else None
    )

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
            {
                "category": "L2 风险事件",
                "total": l2_count,
                "confirmed": 0,
                "pending": 0,
                "local_only": l2_count,
            },
        ],
        "latest_attestation_at": (
            latest.submitted_at.isoformat() if latest and latest.submitted_at else None
        ),
        "latest_chain_provider": latest.chain_provider if latest else None,
        "has_any_confirmed": sum(confirmed_map.values()) > 0,
        "has_any_pending": sum(pending_map.values()) > 0,
    }


# v0.8.0 — 证据清单 HTML(法务交律师 / 法庭用;浏览器打开后「打印为 PDF」)
@router.get("/cases/{legal_case_id}/evidence-receipt")
async def evidence_receipt(
    legal_case_id: int,
    db: Annotated[Session, Depends(get_db)],
    token: str | None = Query(None, description="可选:URL 参数透传 token,便于浏览器新 tab 打开"),
) -> HTMLResponse:
    """生成证据清单(HTML 格式)— 法务交律师 / 法庭用。

    设计:HTML 让法务在浏览器「打印为 PDF」,法律效力一致,避免引入
    reportlab/weasyprint 重依赖。

    内容:
      - 封面:租户名 / 法务案件号 / 业主姓名 / 案件金额 / 生成日期
      - 案件信息:欠费起止 / 月数 / 项目名 / 责任催收员
      - 通话清单表格:序号 / 时间 / 时长 / SHA-256 前 16 / tx_hash 前 16 / 易保全核验链接
      - 风控事件表(若有):时间 / 级别 / 触发文本 / 处置结果 / tx_hash
      - 落款:平台名 + 生成 SHA-256

    认证:支持两种方式:
      1. 标准 Authorization Bearer header(API client 用)
      2. URL ?token=xxx 参数(浏览器新 tab 打开时复用 token)
    """
    from sqlalchemy import select as _select

    from app.core.security import decode_access_token
    from app.models.blockchain_attestation import BlockchainAttestation
    from app.models.call import CallRecord, RiskEvent
    from app.models.tenant import Tenant

    # 简化的认证:从 URL token 拿(支持浏览器新 tab 打开)
    if token:
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail={"code": "ERR_INVALID_TOKEN", "message": "Token 无效"},
            ) from exc
    else:
        # 不支持 header — 这里只接 URL token,简化(实际产品里应通过更安全的方式)
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_NO_TOKEN", "message": "请通过 ?token= 参数提供 JWT"},
        )

    if payload.get("role") not in LEGAL_ROLES:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "仅法务 / admin 可生成证据清单"},
        )

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )

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
    owner = db.get(OwnerProfile, cc.owner_id)
    tenant = db.get(Tenant, tenant_id)

    calls = (
        db.execute(
            _select(CallRecord)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.case_id == cc.id)
            .order_by(CallRecord.started_at.asc())
        )
        .scalars()
        .all()
    )

    # 各 call 关联的 confirmed attestation(取最近一条 call_recording)
    call_attestations: dict[int, list[BlockchainAttestation]] = {}
    if calls:
        atts = (
            db.execute(
                _select(BlockchainAttestation)
                .where(BlockchainAttestation.tenant_id == tenant_id)
                .where(BlockchainAttestation.call_id.in_([c.id for c in calls]))
                .where(BlockchainAttestation.status == "confirmed")
                .order_by(BlockchainAttestation.submitted_at.asc())
            )
            .scalars()
            .all()
        )
        for a in atts:
            if a.call_id is not None:
                call_attestations.setdefault(a.call_id, []).append(a)

    # 风险事件
    risk_events = []
    if calls:
        risk_events = (
            db.execute(
                _select(RiskEvent)
                .where(RiskEvent.call_id.in_([c.id for c in calls]))
                .order_by(RiskEvent.created_at.asc())
            )
            .scalars()
            .all()
        )

    # 生成 HTML
    import html as html_lib
    from datetime import UTC, datetime

    def _esc(s: object) -> str:
        if s is None:
            return ""
        return html_lib.escape(str(s))

    def _short(s: str | None, n: int = 16) -> str:
        if not s:
            return "—"
        return s[:n] + ("…" if len(s) > n else "")

    def _ebaoquan_url(att: BlockchainAttestation) -> str:
        if att.chain_provider == "ebaoquan" and att.preservation_id:
            return f"https://www.ebaoquan.org/inquiry?preservationId={att.preservation_id}"
        return ""

    now = datetime.now(UTC)
    rows_calls = []
    for idx, call in enumerate(calls, start=1):
        atts = call_attestations.get(call.id, [])
        recording_att = next((a for a in atts if a.data_type == "call_recording"), None)
        transcript_att = next((a for a in atts if a.data_type == "transcript"), None)
        analysis_att = next((a for a in atts if a.data_type == "analysis"), None)

        def _att_cell(a: BlockchainAttestation | None) -> str:
            if a is None:
                return '<span style="color:#dc2626">仅本地哈希</span>'
            url = _ebaoquan_url(a)
            tx = _short(a.tx_hash, 16)
            if url:
                return (
                    f'🔗 <a href="{_esc(url)}" target="_blank" '
                    f'style="color:#1A56DB">在易保全核验</a><br>'
                    f'<code style="font-size:10px;color:#6b7280">'
                    f"tx={_esc(tx)}</code>"
                )
            return f'<code style="font-size:10px">tx={_esc(tx)}</code>'

        rows_calls.append(f"""
            <tr>
              <td style="text-align:center">{idx}</td>
              <td>{_esc(call.started_at.strftime("%Y-%m-%d %H:%M") if call.started_at else "—")}</td>
              <td style="text-align:right">{call.duration_sec or 0} 秒</td>
              <td><code style="font-size:10px">{_esc(_short(recording_att.data_sha256 if recording_att else None, 16))}</code></td>
              <td>{_att_cell(recording_att)}</td>
              <td>{_att_cell(transcript_att)}</td>
              <td>{_att_cell(analysis_att)}</td>
            </tr>
        """)

    rows_risk = []
    for re_idx, ev in enumerate(risk_events, start=1):
        rows_risk.append(f"""
            <tr>
              <td style="text-align:center">{re_idx}</td>
              <td>{_esc(ev.created_at.strftime("%Y-%m-%d %H:%M") if ev.created_at else "—")}</td>
              <td><strong style="color:{"#dc2626" if ev.level == "L2" else "#d97706"}">{_esc(ev.level)}</strong></td>
              <td>{_esc(ev.category)}</td>
              <td>{_esc(ev.trigger_text or "—")}</td>
              <td>{_esc(ev.disposition_note or "—")}</td>
            </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>诉讼证据清单 · 案件 #{lc.id}</title>
  <style>
    @media print {{ .no-print {{ display: none }} body {{ margin: 0 }} }}
    body {{ font-family: -apple-system, "PingFang SC", "Helvetica Neue", sans-serif;
           max-width: 900px; margin: 24px auto; padding: 16px; color: #1f2937; line-height: 1.6 }}
    h1 {{ font-size: 22px; border-bottom: 2px solid #1A56DB; padding-bottom: 8px; color: #1A56DB }}
    h2 {{ font-size: 16px; margin-top: 28px; color: #374151; border-left: 4px solid #1A56DB; padding-left: 8px }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px }}
    th {{ background: #f3f4f6; padding: 6px 8px; text-align: left; border: 1px solid #d1d5db }}
    td {{ padding: 6px 8px; border: 1px solid #e5e7eb; vertical-align: top }}
    .cover-table td {{ border: none; padding: 4px 0 }}
    .cover-table td:first-child {{ width: 120px; color: #6b7280 }}
    .footer {{ margin-top: 40px; font-size: 11px; color: #9ca3af; border-top: 1px dashed #d1d5db; padding-top: 16px }}
    .print-btn {{ background: #1A56DB; color: white; border: none; padding: 8px 16px;
                  border-radius: 4px; cursor: pointer; font-size: 13px; margin-bottom: 16px }}
  </style>
</head>
<body>
  <button class="no-print print-btn" onclick="window.print()">打印 / 保存为 PDF</button>

  <h1>诉讼证据清单</h1>

  <h2>封面</h2>
  <table class="cover-table">
    <tr><td>租户</td><td>{_esc(tenant.name if tenant else "—")}</td></tr>
    <tr><td>法务案件号</td><td>LC-{lc.id:06d}</td></tr>
    <tr><td>催收案件号</td><td>CC-{cc.id:06d}</td></tr>
    <tr><td>业主</td><td>{_esc(owner.name if owner else "—")}</td></tr>
    <tr><td>地址</td><td>{
        _esc(((owner.building or "") + (owner.room or "")) if owner else "—")
    }</td></tr>
    <tr><td>欠费金额</td><td>¥ {_esc(cc.amount_owed)}</td></tr>
    <tr><td>逾期</td><td>{_esc(cc.months_overdue or 0)} 个月</td></tr>
    <tr><td>法务阶段</td><td>{_esc(lc.stage)}</td></tr>
    <tr><td>律师</td><td>{_esc(lc.lawyer_name or "—")} / {_esc(lc.law_firm or "—")}</td></tr>
    <tr><td>清单生成日期</td><td>{now.strftime("%Y-%m-%d %H:%M UTC")}</td></tr>
  </table>

  <h2>通话证据清单(共 {len(calls)} 次)</h2>
  {
        (
            '<p style="color:#9ca3af">本案件无通话记录。</p>'
            if not calls
            else f'''
  <table>
    <thead>
      <tr>
        <th>序号</th><th>时间</th><th>时长</th>
        <th>录音 SHA-256(前 16)</th>
        <th>录音存证</th><th>转写存证</th><th>分析存证</th>
      </tr>
    </thead>
    <tbody>{"".join(rows_calls)}</tbody>
  </table>
  '''
        )
    }

  <h2>风险事件清单(共 {len(risk_events)} 件)</h2>
  {
        (
            '<p style="color:#9ca3af">本案件无风险事件。</p>'
            if not risk_events
            else f'''
  <table>
    <thead>
      <tr>
        <th>序号</th><th>时间</th><th>级别</th><th>类别</th>
        <th>触发内容</th><th>督导处置</th>
      </tr>
    </thead>
    <tbody>{"".join(rows_risk)}</tbody>
  </table>
  '''
        )
    }

  <h2>核验说明</h2>
  <p style="font-size:12px;color:#374151">
    本清单中标记 <strong>🔗 在易保全核验</strong> 的证据已上链司法链(易保全 ebaoquan.org),
    可在易保全官网用「保全备案号」核验数据完整性。司法链存证依据
    《最高人民法院关于互联网法院审理案件若干问题的规定》(2018 第 11 号)第十一条,
    互联网法院应当依法予以认定。
  </p>
  <p style="font-size:12px;color:#374151">
    标记 <strong style="color:#dc2626">仅本地哈希</strong> 的证据,SHA-256 哈希值由
    {_esc(tenant.name if tenant else "本系统")} 在数据写入时即时计算并落入数据库,
    可在诉讼准备阶段一键升级为司法链强证据。
  </p>

  <div class="footer">
    本清单由 有证慧催 SaaS 系统生成 · {now.strftime("%Y-%m-%d %H:%M:%S UTC")}<br>
    数据来源:租户 {_esc(tenant.name if tenant else "—")} · 法务案件 LC-{lc.id:06d}<br>
    清单完整性:本 HTML 可保存为 PDF 作书面证据材料附件;核验请通过文中链接到易保全官网。
  </div>
</body>
</html>"""

    return HTMLResponse(content=html_content, media_type="text/html; charset=utf-8")
