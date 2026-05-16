"""v1.6.4 — 督导团队报表 API。

GET /api/v1/supervisor/team-stats?period_days={7|30|90}

返回：
- 通话量趋势（每日 outbound + connected）
- 回款转化漏斗（拨打 → 接通 → 承诺 → 缴清）
- 团队成员排名（通话数 / 接通率 / 承诺数 / 缴清金额）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase
from app.models.user import UserAccount

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "superadmin")


@router.get("/team-stats")
async def get_team_stats(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    period_days: int = Query(30, ge=1, le=365),
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前角色未关联租户"},
        )
    tenant_id = int(tenant_id)

    now = datetime.now(UTC)
    period_end = now
    period_start = now - timedelta(days=period_days)

    # ── 1. 通话量趋势（按天 group） ─────────────────────────
    day_expr = func.date_trunc("day", CallRecord.started_at)
    trend_rows = db.execute(
        select(
            day_expr.label("day"),
            func.count(CallRecord.id).label("outbound"),
            func.sum(case((CallRecord.status == "completed", 1), else_=0)).label("connected"),
        )
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= period_start,
            CallRecord.started_at <= period_end,
        )
        .group_by(day_expr)
        .order_by(day_expr)
    ).all()
    call_trend = [
        {
            "date": (r.day.date() if isinstance(r.day, datetime) else r.day).isoformat(),
            "outbound": int(r.outbound or 0),
            "connected": int(r.connected or 0),
        }
        for r in trend_rows
    ]

    # ── 2. 回款转化漏斗 ─────────────────────────────────────
    outbound_total = (
        db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.started_at >= period_start,
                CallRecord.started_at <= period_end,
            )
        ).scalar_one()
        or 0
    )
    connected_total = (
        db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.started_at >= period_start,
                CallRecord.started_at <= period_end,
                CallRecord.status == "completed",
            )
        ).scalar_one()
        or 0
    )
    promised_total = (
        db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.started_at >= period_start,
                CallRecord.started_at <= period_end,
                CallRecord.result_tag.in_(("承诺缴", "立即缴")),
            )
        ).scalar_one()
        or 0
    )
    paid_total = (
        db.execute(
            select(func.count(CollectionCase.id)).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= period_start,
            )
        ).scalar_one()
        or 0
    )

    funnel = {
        "outbound": int(outbound_total),
        "connected": int(connected_total),
        "promised": int(promised_total),
        "paid": int(paid_total),
    }

    # ── 3. 团队成员排名 ─────────────────────────────────────
    # 按 caller_user_id 聚合，限本租户内 agent 角色
    agg_rows = db.execute(
        select(
            CallRecord.caller_user_id,
            func.count(CallRecord.id).label("total"),
            func.sum(case((CallRecord.status == "completed", 1), else_=0)).label("connected"),
            func.sum(
                case(
                    (CallRecord.result_tag.in_(("承诺缴", "立即缴")), 1),
                    else_=0,
                )
            ).label("promised"),
        )
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= period_start,
            CallRecord.started_at <= period_end,
        )
        .group_by(CallRecord.caller_user_id)
    ).all()

    # 计算每个用户的回款金额（assigned_to=他 + stage=paid 的 case amount_owed 累计）
    paid_per_user_rows = db.execute(
        select(
            CollectionCase.assigned_to,
            func.coalesce(func.sum(CollectionCase.amount_owed), 0).label("paid"),
        )
        .where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "paid",
            CollectionCase.updated_at >= period_start,
        )
        .group_by(CollectionCase.assigned_to)
    ).all()
    paid_by_user = {r.assigned_to: float(r.paid or 0) for r in paid_per_user_rows}

    # 拼接 user 名称（按 user_id 单独查）
    user_ids = [r.caller_user_id for r in agg_rows if r.caller_user_id]
    name_by_id: dict[int, str] = {}
    if user_ids:
        for u in db.execute(
            select(UserAccount.id, UserAccount.name).where(UserAccount.id.in_(user_ids))
        ).all():
            name_by_id[u.id] = u.name

    # 按通话数倒序
    team_ranking = []
    for r in sorted(agg_rows, key=lambda x: -(x.total or 0)):
        if not r.caller_user_id:
            continue
        total = int(r.total or 0)
        connected = int(r.connected or 0)
        team_ranking.append(
            {
                "user_id": r.caller_user_id,
                "name": name_by_id.get(r.caller_user_id, f"用户#{r.caller_user_id}"),
                "calls": total,
                "connected": connected,
                "connect_rate": round(connected / total, 4) if total else 0.0,
                "promises": int(r.promised or 0),
                "paid_amount": f"{paid_by_user.get(r.caller_user_id, 0):.2f}",
            }
        )

    return {
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
        "period_days": period_days,
        "call_trend": call_trend,
        "funnel": funnel,
        "team_ranking": team_ranking,
    }
