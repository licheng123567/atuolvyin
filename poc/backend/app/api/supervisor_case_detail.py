"""v1.5.7 S3 — 督导侧案件详情 API。

GET /api/v1/supervisor/cases/{case_id}

督导查看本租户案件全貌，含基本信息、近期通话、案件时间线。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.crypto import mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import AnalysisResult, CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.user import UserAccount

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "legal")
# v1.6 — legal 角色（物业法务对接人）可只读案件全貌（限本租户）；律所/律师不在内


@router.get("/cases/{case_id}")
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前角色未关联租户"},
        )
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )

    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    project = db.get(Project, case.project_id) if case.project_id else None
    agent = db.get(UserAccount, case.assigned_to) if case.assigned_to else None

    calls = db.execute(
        select(CallRecord)
        .where(CallRecord.case_id == case_id)
        .order_by(desc(CallRecord.started_at))
        .limit(10)
    ).scalars().all()

    recent_calls: list[dict] = []
    for c in calls:
        analysis = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == c.id).limit(1)
        ).scalars().first()
        agent_name = ""
        if c.caller_user_id:
            ua = db.get(UserAccount, c.caller_user_id)
            agent_name = ua.name if ua else ""
        recent_calls.append({
            "id": c.id,
            "date": c.started_at.isoformat() if c.started_at else None,
            "duration_sec": c.duration_sec,
            "agent": agent_name,
            "result_tag": c.result_tag,
            "emotion_tag": c.emotion_tag,
            "ai_summary": (analysis.summary if analysis else None),
            "risk_flagged": c.risk_flagged,
        })

    timeline: list[dict] = []
    for c in calls:
        timeline.append({
            "time": c.started_at.isoformat() if c.started_at else None,
            "type": "call",
            "desc": f"通话 {c.duration_sec or 0}s · 结果：{c.result_tag or '—'}",
        })
    if case.stage == "escalated":
        timeline.append({
            "time": case.updated_at.isoformat() if case.updated_at else None,
            "type": "escalate",
            "desc": "案件已升级到督导处理",
        })
    timeline.sort(key=lambda x: x["time"] or "", reverse=True)

    phone_masked = mask_phone(owner.phone_enc) if owner and owner.phone_enc else None

    # v1.6 — 真实账单数据（如果导入时录入）+ 工单
    from app.models.work import WorkOrder
    work_orders = db.execute(
        select(WorkOrder)
        .where(WorkOrder.case_id == case_id)
        .order_by(desc(WorkOrder.created_at))
        .limit(20)
    ).scalars().all()
    work_orders_out = [
        {
            "id": w.id,
            "order_type": w.order_type,
            "description": w.description,
            "status": w.status,
            "priority": w.priority,
            "resolution": w.resolution,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in work_orders
    ]

    return {
        "id": case.id,
        "owner_name": owner.name if owner else None,
        "building": owner.building if owner else None,
        "room": owner.room if owner else None,
        "phone_masked": phone_masked,
        "amount": float(case.amount_owed) if case.amount_owed is not None else None,
        "principal_amount": float(case.principal_amount) if case.principal_amount is not None else None,
        "late_fee_amount": float(case.late_fee_amount) if case.late_fee_amount is not None else None,
        "bill_period_start": case.bill_period_start.isoformat() if case.bill_period_start else None,
        "bill_period_end": case.bill_period_end.isoformat() if case.bill_period_end else None,
        "arrears_reason": case.arrears_reason,
        "months_overdue": case.months_overdue,
        "status": case.stage,
        "agent_name": agent.name if agent else None,
        "project_name": project.name if project else None,
        "project_id": case.project_id,
        # v1.6.3 — 项目基本信息（合同 + 收费），让案件详情看到所属项目的合规依据
        "project_info": (
            {
                "name": project.name,
                "charge_rate_text": project.charge_rate_text,
                "charge_period": project.charge_period,
                "contract_type": project.contract_type,
                "contract_start_date": project.contract_start_date.isoformat() if project.contract_start_date else None,
                "contract_end_date": project.contract_end_date.isoformat() if project.contract_end_date else None,
                "contract_attachment_key": project.contract_attachment_key,
                "contract_attachment_filename": project.contract_attachment_filename,
                "charge_notes": project.charge_notes,
            }
            if project
            else None
        ),
        "notes": case.notes,
        "recent_calls": recent_calls,
        "timeline": timeline[:20],
        "work_orders": work_orders_out,
    }
