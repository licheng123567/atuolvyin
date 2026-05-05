from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload
from app.models.risk import RiskKeyword
from app.schemas.common import PaginatedResponse
from app.schemas.risk import RiskKeywordCreate, RiskKeywordOut, RiskKeywordUpdate

router = APIRouter()

_ALLOWED_ROLES = {"admin", "platform_super"}


def _check_auth(payload: dict) -> tuple[str, Optional[int]]:
    role = payload.get("role", "")
    if role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN,
                            detail={"code": "ERR_403", "message": "insufficient role"})
    tenant_id = payload.get("tenant_id")
    return role, int(tenant_id) if tenant_id else None


@router.get("/risk-keywords", response_model=PaginatedResponse[RiskKeywordOut])
async def list_risk_keywords(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    category: Optional[str] = Query(None),
    speaker: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    role, tenant_id = _check_auth(payload)
    stmt = select(RiskKeyword)
    if role == "admin":
        stmt = stmt.where(
            or_(RiskKeyword.tenant_id == tenant_id, RiskKeyword.tenant_id.is_(None))
        )
    if category:
        stmt = stmt.where(RiskKeyword.category == category)
    if speaker:
        stmt = stmt.where(RiskKeyword.speaker == speaker)
    if is_active is not None:
        stmt = stmt.where(RiskKeyword.is_active == is_active)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        items=[RiskKeywordOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/risk-keywords", response_model=RiskKeywordOut, status_code=http_status.HTTP_201_CREATED)
async def create_risk_keyword(
    body: RiskKeywordCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
):
    role, caller_tenant_id = _check_auth(payload)
    if role == "admin":
        if body.tenant_id is not None and body.tenant_id != caller_tenant_id:
            raise HTTPException(status_code=403, detail={"code": "ERR_403", "message": "cross-tenant denied"})
        effective_tenant = caller_tenant_id
    else:
        effective_tenant = body.tenant_id  # platform_super may use None

    kw = RiskKeyword(
        tenant_id=effective_tenant,
        category=body.category,
        speaker=body.speaker,
        level=body.level,
        keyword=body.keyword,
    )
    db.add(kw)
    db.flush()
    return RiskKeywordOut.model_validate(kw)


@router.patch("/risk-keywords/{keyword_id}", response_model=RiskKeywordOut)
async def update_risk_keyword(
    keyword_id: int,
    body: RiskKeywordUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
):
    role, tenant_id = _check_auth(payload)
    kw = db.get(RiskKeyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail={"code": "ERR_404", "message": "not found"})
    if role == "admin" and kw.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail={"code": "ERR_403", "message": "cannot modify platform preset"})
    if body.is_active is not None:
        kw.is_active = body.is_active
    if body.level is not None:
        kw.level = body.level
    db.flush()
    return RiskKeywordOut.model_validate(kw)


@router.delete("/risk-keywords/{keyword_id}", response_model=RiskKeywordOut)
async def delete_risk_keyword(
    keyword_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
):
    role, tenant_id = _check_auth(payload)
    kw = db.get(RiskKeyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail={"code": "ERR_404", "message": "not found"})
    if role == "admin" and kw.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail={"code": "ERR_403", "message": "cannot delete platform preset"})
    kw.is_active = False
    db.flush()
    return RiskKeywordOut.model_validate(kw)
