"""Sprint 13.1 — 区块链核验入口（PRD §20.3 v1.1）。

无需登录的公开端点。法务/业主/法庭通过 tx_hash 校验数据是否上过链。
为隐私安全：仅返回非敏感元数据（tenant_name + call_id + 数据 hash + 上链时间），
不展示业主真名 / 电话 / 欠款金额。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.blockchain_attestation import BlockchainAttestation
from app.models.tenant import Tenant

router = APIRouter()


class VerifyResponse(BaseModel):
    tx_hash: str
    block_height: int | None  # v0.8.0 改 None 允许:pending / failed 行可能无
    chain_provider: str
    chain_endpoint: str | None
    data_sha256: str
    data_type: str
    status: str
    submitted_at: str
    confirmed_at: str | None
    tenant_name: str | None
    call_id: int | None
    started_at: str | None
    duration_sec: int | None
    # v0.8.0 — 易保全保全备案号 + 官方核验 URL(让前端展示「在易保全官网查」按钮)
    preservation_id: int | None = None
    provider_evidence_id: int | None = None
    ebaoquan_verify_url: str | None = None


@router.get("/verify/{tx_hash}", response_model=VerifyResponse)
def verify_attestation(
    tx_hash: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")],
    db: Annotated[Session, Depends(get_db)],
) -> VerifyResponse:
    att = db.execute(
        select(BlockchainAttestation).where(BlockchainAttestation.tx_hash == tx_hash)
    ).scalar_one_or_none()
    if att is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "未找到该 tx_hash 的存证记录"},
        )

    # Tenant name is OK to expose — appears on the legal evidence bundle anyway
    tenant = db.get(Tenant, att.tenant_id)
    meta = att.payload_metadata or {}

    # v0.8.0 — 易保全官方核验 URL(若有 preservation_id 拼跳转地址)
    # 用户决策 C2:借易保全公信力 — 律师/法庭直接在易保全官网核验更可信
    ebaoquan_verify_url: str | None = None
    if att.chain_provider == "ebaoquan" and att.preservation_id is not None:
        # 易保全官方核验:用户在 https://www.ebaoquan.org/inquiry 输入保全备案号
        # 当前没固定的 deep-link 参数,跳查询首页让用户输入
        ebaoquan_verify_url = (
            f"https://www.ebaoquan.org/inquiry?preservationId={att.preservation_id}"
        )

    return VerifyResponse(
        tx_hash=att.tx_hash,
        block_height=att.block_height,
        chain_provider=att.chain_provider,
        chain_endpoint=att.chain_endpoint,
        data_sha256=att.data_sha256,
        data_type=att.data_type,
        status=att.status,
        submitted_at=att.submitted_at.isoformat(),
        confirmed_at=att.confirmed_at.isoformat() if att.confirmed_at else None,
        tenant_name=tenant.name if tenant else None,
        call_id=meta.get("call_id"),
        started_at=meta.get("started_at"),
        duration_sec=meta.get("duration_sec"),
        preservation_id=att.preservation_id,
        provider_evidence_id=att.provider_evidence_id,
        ebaoquan_verify_url=ebaoquan_verify_url,
    )
