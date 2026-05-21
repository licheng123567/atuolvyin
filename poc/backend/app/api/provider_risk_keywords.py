"""v1.0.0 — 服务商风控关键词管理(对齐物业 admin)。

诱因:用户反馈服务商需要 1:1 还原物业 admin 的风控关键词管理。

scope:
  - 服务商 admin 只看 / 改 自己服务商的关键词(provider_id == self_provider)
  - 也能看平台预置(tenant_id IS NULL AND provider_id IS NULL),但只读
  - 看不到其他服务商或物业租户的关键词
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_provider_roles
from app.models.risk import RiskKeyword
from app.models.tenant import UserTenantMembership
from app.schemas.common import PaginatedResponse
from app.schemas.risk import RiskKeywordCreate, RiskKeywordOut, RiskKeywordUpdate

router = APIRouter()

PROVIDER_ADMIN_ROLES = ("admin",)
_MAX_PAGE_SIZE = 100


def _resolve_provider_id(payload: dict, db: Session) -> int:
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token payload"},
        )
    membership = (
        db.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.user_id == user_id)
            .where(UserTenantMembership.provider_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if membership is None or membership.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定任何服务商"},
        )
    return int(membership.provider_id)


def _assert_can_modify(provider_id: int, kw: RiskKeyword) -> None:
    """服务商 admin 只能改自己的关键词;不能改平台预置或别人的。"""
    if kw.provider_id is None or kw.provider_id != provider_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_403", "message": "只能管理本服务商的风控关键词"},
        )


@router.get("/risk-keywords", response_model=PaginatedResponse[RiskKeywordOut])
async def list_risk_keywords(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    category: str | None = Query(None),
    speaker: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=_MAX_PAGE_SIZE),
) -> PaginatedResponse[RiskKeywordOut]:
    provider_id = _resolve_provider_id(payload, db)

    # 服务商看本服务商关键词 + 平台预置
    stmt = select(RiskKeyword).where(
        or_(
            RiskKeyword.provider_id == provider_id,
            (RiskKeyword.tenant_id.is_(None)) & (RiskKeyword.provider_id.is_(None)),
        )
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
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/risk-keywords",
    response_model=RiskKeywordOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_risk_keyword(
    body: RiskKeywordCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> RiskKeywordOut:
    provider_id = _resolve_provider_id(payload, db)

    # 服务商创建的关键词自动归属本服务商(provider_id 必填,tenant_id 强制 NULL)
    kw = RiskKeyword(
        tenant_id=None,
        provider_id=provider_id,
        category=body.category,
        speaker=body.speaker,
        level=body.level,
        keyword=body.keyword,
    )
    db.add(kw)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_409", "message": "本服务商已存在相同关键词"},
        ) from None
    db.refresh(kw)
    return RiskKeywordOut.model_validate(kw)


@router.patch("/risk-keywords/{keyword_id}", response_model=RiskKeywordOut)
async def update_risk_keyword(
    keyword_id: int,
    body: RiskKeywordUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> RiskKeywordOut:
    provider_id = _resolve_provider_id(payload, db)
    kw = db.get(RiskKeyword, keyword_id)
    if not kw:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_404", "message": "not found"},
        )
    _assert_can_modify(provider_id, kw)
    if body.is_active is not None:
        kw.is_active = body.is_active
    if body.level is not None:
        kw.level = body.level
    db.commit()
    db.refresh(kw)
    return RiskKeywordOut.model_validate(kw)


@router.delete("/risk-keywords/{keyword_id}", response_model=RiskKeywordOut)
async def delete_risk_keyword(
    keyword_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> RiskKeywordOut:
    provider_id = _resolve_provider_id(payload, db)
    kw = db.get(RiskKeyword, keyword_id)
    if not kw:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_404", "message": "not found"},
        )
    _assert_can_modify(provider_id, kw)
    kw.is_active = False
    db.commit()
    db.refresh(kw)
    return RiskKeywordOut.model_validate(kw)
