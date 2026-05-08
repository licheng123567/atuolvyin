"""v1.6.4 — 督导侧升级案件列表 API。

GET /api/v1/supervisor/escalated-cases?page=&page_size=

返回本租户内 stage=escalated 的案件分页列表，督导用于「升级案件处理」页。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, select, func
from sqlalchemy.orm import Session

from app.core.crypto import mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.user import UserAccount

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "platform_superadmin")


@router.get("/escalated-cases")
async def list_escalated_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    tenant_id = int(tenant_id)

    base = (
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"), UserAccount.name.label("agent_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id, isouter=True)
        .join(UserAccount, UserAccount.id == CollectionCase.assigned_to, isouter=True)
        .where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "escalated",
        )
    )
    total = db.execute(
        select(func.count(CollectionCase.id)).where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "escalated",
        )
    ).scalar_one()

    rows = db.execute(
        base.order_by(desc(CollectionCase.priority_score), desc(CollectionCase.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for case, owner, project_name, agent_name in rows:
        amount = float(case.amount_owed) if case.amount_owed is not None else 0.0
        # 简易优先级判定：欠费 > 1.5w 或欠 > 12 月 → high
        priority = (
            "high"
            if amount > 15000 or (case.months_overdue or 0) > 12
            else "medium"
        )
        items.append(
            {
                "id": case.id,
                "owner_name": owner.name,
                "building": (owner.building or "") + (owner.room or ""),
                "phone_masked": mask_phone(owner.phone_enc) if owner.phone_enc else "—",
                "amount": amount,
                "months_overdue": case.months_overdue or 0,
                "reason": case.notes or case.arrears_reason or "—",
                "raised_by": agent_name or "—",
                "raised_at": case.updated_at.strftime("%Y-%m-%d %H:%M") if case.updated_at else "—",
                "priority": priority,
                "project_name": project_name or "—",
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
