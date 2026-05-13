"""v1.9.0 — admin 后台：合作律所 + 律师函模板的 CRUD endpoints。

物业 admin 自管：合作律所列表（不耦合现有平台 LawFirm）+ 律师函/催告函模板。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.legal_internal import (
    InternalLegalLetterTemplate,
    PartnerLawFirm,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_internal import (
    InternalLegalLetterTemplateCreate,
    InternalLegalLetterTemplateOut,
    InternalLegalLetterTemplateUpdate,
    PartnerLawFirmCreate,
    PartnerLawFirmOut,
    PartnerLawFirmUpdate,
)
from app.services.audit import log_audit

router = APIRouter()
# legal 角色起草律师函时也要选合作律所，所以 GET 也放给 legal
ADMIN_ROLES = ("admin",)
READ_ROLES = ("admin", "legal", "supervisor")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    return int(tenant_id)


# ════════════════════════════════════════════════════════════════
#  PartnerLawFirm CRUD
# ════════════════════════════════════════════════════════════════
def _firm_to_out(f: PartnerLawFirm) -> PartnerLawFirmOut:
    return PartnerLawFirmOut(
        id=f.id,
        tenant_id=f.tenant_id,
        name=f.name,
        contact_name=f.contact_name,
        contact_phone_masked=mask_phone(f.contact_phone_enc) if f.contact_phone_enc else None,
        contact_email=f.contact_email,
        seal_attachment_key=f.seal_attachment_key,
        notes=f.notes,
        is_active=f.is_active,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


@router.get(
    "/partner-law-firms",
    response_model=PaginatedResponse[PartnerLawFirmOut],
)
def list_partner_law_firms(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    only_active: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[PartnerLawFirmOut]:
    tenant_id = _require_tenant(payload)
    stmt = select(PartnerLawFirm).where(PartnerLawFirm.tenant_id == tenant_id)
    if only_active:
        stmt = stmt.where(PartnerLawFirm.is_active.is_(True))
    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(desc(PartnerLawFirm.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[_firm_to_out(f) for f in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/partner-law-firms",
    response_model=PartnerLawFirmOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_partner_law_firm(
    body: PartnerLawFirmCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PartnerLawFirmOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")

    existing = db.execute(
        select(PartnerLawFirm).where(
            PartnerLawFirm.tenant_id == tenant_id,
            PartnerLawFirm.name == body.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_DUPLICATE", "message": "律所名称已存在"},
        )
    firm = PartnerLawFirm(
        tenant_id=tenant_id,
        name=body.name,
        contact_name=body.contact_name,
        contact_phone_enc=encrypt_phone(body.contact_phone) if body.contact_phone else None,
        contact_email=body.contact_email,
        notes=body.notes,
        is_active=True,
    )
    db.add(firm)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="partner_law_firm.created",
        target_type="partner_law_firm",
        target_id=firm.id,
        payload={"name": body.name},
    )
    db.commit()
    db.refresh(firm)
    return _firm_to_out(firm)


@router.patch("/partner-law-firms/{firm_id}", response_model=PartnerLawFirmOut)
def update_partner_law_firm(
    firm_id: int,
    body: PartnerLawFirmUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PartnerLawFirmOut:
    tenant_id = _require_tenant(payload)
    firm = db.get(PartnerLawFirm, firm_id)
    if firm is None or firm.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "合作律所不存在"},
        )
    data = body.model_dump(exclude_unset=True)
    if "contact_phone" in data:
        firm.contact_phone_enc = (
            encrypt_phone(data.pop("contact_phone")) if data["contact_phone"] else None
        )
    for k, v in data.items():
        setattr(firm, k, v)
    db.commit()
    db.refresh(firm)
    return _firm_to_out(firm)


@router.delete(
    "/partner-law-firms/{firm_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def delete_partner_law_firm(
    firm_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant_id = _require_tenant(payload)
    firm = db.get(PartnerLawFirm, firm_id)
    if firm is None or firm.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "合作律所不存在"},
        )
    # 软删：is_active=False；保留历史 action 引用
    firm.is_active = False
    db.commit()


# ════════════════════════════════════════════════════════════════
#  InternalLegalLetterTemplate CRUD
# ════════════════════════════════════════════════════════════════
def _tpl_to_out(t: InternalLegalLetterTemplate) -> InternalLegalLetterTemplateOut:
    return InternalLegalLetterTemplateOut(
        id=t.id,
        tenant_id=t.tenant_id,
        name=t.name,
        category=t.category,
        body_md=t.body_md,
        variables=t.variables,
        is_active=t.is_active,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get(
    "/internal-letter-templates",
    response_model=PaginatedResponse[InternalLegalLetterTemplateOut],
)
def list_letter_templates(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    only_active: bool = Query(True),
    category: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaginatedResponse[InternalLegalLetterTemplateOut]:
    tenant_id = _require_tenant(payload)
    stmt = select(InternalLegalLetterTemplate).where(
        InternalLegalLetterTemplate.tenant_id == tenant_id
    )
    if only_active:
        stmt = stmt.where(InternalLegalLetterTemplate.is_active.is_(True))
    if category:
        stmt = stmt.where(InternalLegalLetterTemplate.category == category)
    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(desc(InternalLegalLetterTemplate.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[_tpl_to_out(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/internal-letter-templates",
    response_model=InternalLegalLetterTemplateOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_letter_template(
    body: InternalLegalLetterTemplateCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InternalLegalLetterTemplateOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = payload.get("role", "")

    existing = db.execute(
        select(InternalLegalLetterTemplate).where(
            InternalLegalLetterTemplate.tenant_id == tenant_id,
            InternalLegalLetterTemplate.name == body.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_DUPLICATE", "message": "模板名称已存在"},
        )
    tpl = InternalLegalLetterTemplate(
        tenant_id=tenant_id,
        name=body.name,
        category=body.category,
        body_md=body.body_md,
        variables=[v.model_dump() for v in body.variables] if body.variables else None,
        is_active=True,
    )
    db.add(tpl)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="internal_letter_template.created",
        target_type="internal_legal_letter_template",
        target_id=tpl.id,
        payload={"name": body.name, "category": body.category},
    )
    db.commit()
    db.refresh(tpl)
    return _tpl_to_out(tpl)


@router.patch(
    "/internal-letter-templates/{tpl_id}",
    response_model=InternalLegalLetterTemplateOut,
)
def update_letter_template(
    tpl_id: int,
    body: InternalLegalLetterTemplateUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InternalLegalLetterTemplateOut:
    tenant_id = _require_tenant(payload)
    tpl = db.get(InternalLegalLetterTemplate, tpl_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "模板不存在"},
        )
    data = body.model_dump(exclude_unset=True)
    if "variables" in data and data["variables"] is not None:
        # variables 可能是 LetterVariableSpec 的 dict（已通过 pydantic 解析）
        data["variables"] = [
            v if isinstance(v, dict) else v.model_dump() for v in data["variables"]
        ]
    for k, v in data.items():
        setattr(tpl, k, v)
    db.commit()
    db.refresh(tpl)
    return _tpl_to_out(tpl)


@router.delete(
    "/internal-letter-templates/{tpl_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def delete_letter_template(
    tpl_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant_id = _require_tenant(payload)
    tpl = db.get(InternalLegalLetterTemplate, tpl_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "模板不存在"},
        )
    tpl.is_active = False
    db.commit()
