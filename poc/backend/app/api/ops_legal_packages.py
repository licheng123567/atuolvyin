"""v0.5.5 — 平台 OPS 服务包目录后台 (PRD §20.4 「服务包定价归属」)。

法务服务包是平台级目录(`tenant_id IS NULL`),4 档(律师函 / 诉前调解 / 小额诉讼 /
完整代理)对所有租户统一可见。定价归属:律所报价 → OPS 维护 → 全租户共享。

本模块给 OPS 提供在线改价/改描述能力,避免之前只能改 seed_demo.py 的窘境。
范围最小:只改单价/平台抽成率/描述/排序/启用,不新增/删除包(包目录由产品 + 数据迁移
确定)。租户专属价(`tenant_id != NULL` 的行)不在本目录管理,未来按需扩展。

端点:
  GET   /api/v1/ops/legal-packages          全部 4 档(含 disabled)
  PATCH /api/v1/ops/legal-packages/{id}     改 price/platform_fee_rate/description/...
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.audit import AuditLog
from app.models.legal_conversion import LegalServicePackage
from app.models.user import UserAccount
from app.schemas.legal_conversion import LegalServicePackageOut

router = APIRouter()

OPS_ROLES = ("ops", "superadmin")


class LegalPackagePatchIn(BaseModel):
    """部分字段更新 — 全部可选。"""

    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=4000)
    price: Decimal | None = Field(None, ge=0)
    platform_fee_rate: Decimal | None = Field(None, ge=0, le=1)
    enabled: bool | None = None
    sort_order: int | None = Field(None, ge=0)


@router.get("/legal-packages", response_model=list[LegalServicePackageOut])
async def list_packages(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[LegalServicePackageOut]:
    """列出平台级所有服务包(含 disabled,按 sort_order)。"""
    rows = (
        db.execute(
            select(LegalServicePackage)
            .where(LegalServicePackage.tenant_id.is_(None))
            .order_by(LegalServicePackage.sort_order, LegalServicePackage.id)
        )
        .scalars()
        .all()
    )
    return [LegalServicePackageOut.model_validate(p) for p in rows]


@router.patch("/legal-packages/{package_id}", response_model=LegalServicePackageOut)
async def patch_package(
    package_id: int,
    body: LegalPackagePatchIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalServicePackageOut:
    pkg = db.get(LegalServicePackage, package_id)
    if pkg is None or pkg.tenant_id is not None:
        # 租户专属价不在 OPS 目录管理范围
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "服务包不存在或非平台级目录项"},
        )

    diff: dict[str, tuple] = {}
    update_data = body.model_dump(exclude_unset=True)
    for field, new_val in update_data.items():
        old_val = getattr(pkg, field)
        if old_val != new_val:
            diff[field] = (
                str(old_val) if isinstance(old_val, Decimal) else old_val,
                str(new_val) if isinstance(new_val, Decimal) else new_val,
            )
            setattr(pkg, field, new_val)

    if diff:
        db.add(
            AuditLog(
                tenant_id=None,  # 平台级操作,无租户上下文
                actor_user_id=user.id,
                actor_role=user.platform_role or "ops",
                action="ops.legal_package.patched",
                target_type="legal_service_package",
                target_id=pkg.id,
                payload={"changes": diff, "package_slug": pkg.slug},
                created_at=datetime.now(UTC),
            )
        )
    db.commit()
    db.refresh(pkg)
    return LegalServicePackageOut.model_validate(pkg)
