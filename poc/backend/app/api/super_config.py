"""Sprint 10 — platform_super extras (PRD §1.x / L1969, L1972).

Endpoints:
  GET   /super/llm-prompts                — list all (latest version per name)
  POST  /super/llm-prompts                — create new prompt (auto-version)
  PATCH /super/llm-prompts/{id}/active    — activate / deactivate (single-active per name)
  GET   /super/blockchain-config          — get current single config (or null)
  PUT   /super/blockchain-config          — upsert config; api_key encrypted
  GET   /super/sms-config                 — get current SMS config (or null)
  PUT   /super/sms-config                 — upsert config; secret_key encrypted
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone  # generic AES helper
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.platform import BlockchainConfig, LLMPromptTemplate, SmsConfig
from app.models.user import UserAccount
from app.schemas.platform import (
    BlockchainConfigIn,
    BlockchainConfigOut,
    LLMPromptActivateIn,
    LLMPromptIn,
    LLMPromptOut,
    SmsConfigIn,
    SmsConfigOut,
)

router = APIRouter()

SUPER_ROLES = ("superadmin",)


def _user_id(payload: dict) -> int:
    uid = payload.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token missing user_id"},
        )
    return int(uid)


# ── L1969 LLM prompt management ─────────────────────────────────────


@router.get("/llm-prompts", response_model=list[LLMPromptOut])
async def list_prompts(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[LLMPromptOut]:
    rows = (
        db.execute(
            select(LLMPromptTemplate).order_by(
                LLMPromptTemplate.name.asc(), LLMPromptTemplate.version.desc()
            )
        )
        .scalars()
        .all()
    )
    return [LLMPromptOut.model_validate(r) for r in rows]


@router.post(
    "/llm-prompts",
    response_model=LLMPromptOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_prompt(
    body: LLMPromptIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LLMPromptOut:
    user_id = _user_id(payload)
    # Auto-bump version: max(version) for this name + 1
    latest_version: int | None = db.execute(
        select(func.max(LLMPromptTemplate.version)).where(LLMPromptTemplate.name == body.name)
    ).scalar_one()
    next_version = (latest_version or 0) + 1

    p = LLMPromptTemplate(
        name=body.name,
        version=next_version,
        body=body.body,
        notes=body.notes,
        is_active=False,
        created_by=user_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return LLMPromptOut.model_validate(p)


@router.patch("/llm-prompts/{prompt_id}/active", response_model=LLMPromptOut)
async def set_prompt_active(
    prompt_id: int,
    body: LLMPromptActivateIn,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LLMPromptOut:
    p = db.get(LLMPromptTemplate, prompt_id)
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "Prompt 不存在"},
        )
    # Only one active version per name — if activating, deactivate siblings first
    if body.is_active:
        db.execute(
            sa_update(LLMPromptTemplate)
            .where(LLMPromptTemplate.name == p.name)
            .where(LLMPromptTemplate.id != p.id)
            .values(is_active=False)
        )
    p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return LLMPromptOut.model_validate(p)


# ── L1972 blockchain config ─────────────────────────────────────────


def _config_to_out(c: BlockchainConfig) -> BlockchainConfigOut:
    return BlockchainConfigOut(
        id=c.id,
        provider=c.provider,
        api_endpoint=c.api_endpoint,
        has_api_key=bool(c.api_key_enc),
        is_active=c.is_active,
        last_failure_at=c.last_failure_at,
        last_failure_reason=c.last_failure_reason,
        updated_at=c.updated_at,
    )


@router.get("/blockchain-config", response_model=BlockchainConfigOut | None)
async def get_blockchain_config(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> BlockchainConfigOut | None:
    c = db.execute(
        select(BlockchainConfig).order_by(desc(BlockchainConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    return _config_to_out(c) if c else None


@router.put("/blockchain-config", response_model=BlockchainConfigOut)
async def put_blockchain_config(
    body: BlockchainConfigIn,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> BlockchainConfigOut:
    c = db.execute(
        select(BlockchainConfig).where(BlockchainConfig.provider == body.provider)
    ).scalar_one_or_none()
    if c is None:
        c = BlockchainConfig(
            provider=body.provider,
            api_endpoint=body.api_endpoint,
            api_key_enc=encrypt_phone(body.api_key) if body.api_key else None,
            is_active=body.is_active,
        )
        db.add(c)
    else:
        c.api_endpoint = body.api_endpoint
        if body.api_key is not None:
            c.api_key_enc = encrypt_phone(body.api_key) if body.api_key else None
        c.is_active = body.is_active
    db.commit()
    db.refresh(c)
    return _config_to_out(c)


# ── 短信中心配置 ─────────────────────────────────────────────────────


def _sms_config_to_out(c: SmsConfig) -> SmsConfigOut:
    return SmsConfigOut(
        id=c.id,
        secret_name=c.secret_name,
        sign_name=c.sign_name,
        otp_template_id=c.otp_template_id,
        has_secret_key=bool(c.secret_key_enc),
        is_active=c.is_active,
        last_failure_at=c.last_failure_at,
        last_failure_reason=c.last_failure_reason,
        updated_at=c.updated_at,
    )


@router.get("/sms-config", response_model=SmsConfigOut | None)
async def get_sms_config(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SmsConfigOut | None:
    c = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    return _sms_config_to_out(c) if c else None


@router.put("/sms-config", response_model=SmsConfigOut)
async def put_sms_config(
    body: SmsConfigIn,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SmsConfigOut:
    c = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    if c is None:
        c = SmsConfig(
            secret_name=body.secret_name,
            secret_key_enc=encrypt_phone(body.secret_key) if body.secret_key else None,
            sign_name=body.sign_name,
            otp_template_id=body.otp_template_id,
            is_active=body.is_active,
        )
        db.add(c)
    else:
        c.secret_name = body.secret_name
        if body.secret_key is not None:
            c.secret_key_enc = encrypt_phone(body.secret_key) if body.secret_key else None
        c.sign_name = body.sign_name
        c.otp_template_id = body.otp_template_id
        c.is_active = body.is_active
    db.commit()
    db.refresh(c)
    return _sms_config_to_out(c)
