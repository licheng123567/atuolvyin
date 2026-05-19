"""v2.2 — 业主公开缴费页：无鉴权，凭 token 查案件账单。

不返回业主手机号（PRD §14 防信息泄露）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.storage import storage
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.payment_link import PaymentLink
from app.services.payment_link import PaymentBreakdown, compute_payable

router = APIRouter()


class PublicPaymentOut(BaseModel):
    owner_name: str
    owner_room: str | None
    payment_mode: str
    payee_name: str | None
    payee_account: str | None
    payee_qr_url: str | None
    payment_instructions: str | None
    breakdown: PaymentBreakdown


@router.get("/payment/{token}", response_model=PublicPaymentOut)
def get_public_payment(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> PublicPaymentOut:
    """业主扫码 / 点链接打开账单页（无需登录）。"""
    link = db.execute(
        select(PaymentLink).where(PaymentLink.token == token)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "缴费链接不存在"},
        )
    if link.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=http_status.HTTP_410_GONE,
            detail={"code": "ERR_LINK_EXPIRED", "message": "缴费链接已失效，请联系物业重新获取"},
        )

    case = db.get(CollectionCase, link.case_id)
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    project = db.get(Project, link.project_id) if link.project_id else None

    qr_url = (
        storage.get_url(project.payee_qr_object_key)
        if project and project.payee_qr_object_key
        else None
    )
    return PublicPaymentOut(
        owner_name=owner.name if owner else "业主",
        owner_room=owner.room if owner else None,
        payment_mode=project.payment_mode if project else "property_self",
        payee_name=project.payee_name if project else None,
        payee_account=project.payee_account if project else None,
        payee_qr_url=qr_url,
        payment_instructions=project.payment_instructions if project else None,
        breakdown=compute_payable(db, case),
    )
