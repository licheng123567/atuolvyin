"""Sprint 16.5 — Service provider admin script library.

D4 — 话术三层归属与权限：
  服务商 admin 可 CRUD 自己 (provider_id == 自家服务商) 范围内的话术；
  GET 列表合并展示平台预置（tenant_id NULL & provider_id NULL）；
  **不可读物业私有话术（属其他租户的数字资产）**。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_provider_roles
from app.models.script import ScriptTemplate
from app.models.tenant import UserTenantMembership
from app.schemas.common import PaginatedResponse
from app.schemas.script import (
    ScriptTemplateCreate,
    ScriptTemplateOut,
    ScriptTemplateUpdate,
)

from .admin_scripts import _to_out, _write_snapshot

router = APIRouter()

PROVIDER_ROLES = ("admin",)  # provider-side admin; access guarded by _provider_id_for checking provider_id
VALID_INTENTS = frozenset({"房屋质量", "经济困难", "服务不满", "联系困难", "其他"})


def _provider_id_for(db: Session, user_id: int) -> int:
    m = (
        db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.role == "admin",
                UserTenantMembership.provider_id.isnot(None),
            )
        )
        .scalars()
        .first()
    )
    if m is None or m.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定服务商"},
        )
    return int(m.provider_id)


def _get_provider_script(
    db: Session, script_id: int, provider_id: int, *, for_write: bool = False
) -> ScriptTemplate:
    """读 = 平台预置 + 本服务商私有；写仅本服务商私有。"""
    stmt = select(ScriptTemplate).where(
        ScriptTemplate.id == script_id,
        or_(
            ScriptTemplate.provider_id == provider_id,
            # 平台预置（无 tenant + 无 provider）
            ScriptTemplate.tenant_id.is_(None) & ScriptTemplate.provider_id.is_(None),
        ),
    )
    script = db.execute(stmt).scalar_one_or_none()
    if not script:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "话术不存在"},
        )
    if for_write and script.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_PLATFORM_READONLY",
                "message": "平台预置话术不可修改",
            },
        )
    return script


@router.get("/scripts", response_model=PaginatedResponse[ScriptTemplateOut])
def list_provider_scripts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None),
    intent: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ScriptTemplateOut]:
    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)

    stmt = select(ScriptTemplate).where(
        or_(
            ScriptTemplate.provider_id == provider_id,
            ScriptTemplate.tenant_id.is_(None) & ScriptTemplate.provider_id.is_(None),
        )
    )
    if q:
        stmt = stmt.where(
            or_(
                ScriptTemplate.title.ilike(f"%{q}%"),
                ScriptTemplate.content.ilike(f"%{q}%"),
            )
        )
    if intent:
        stmt = stmt.where(ScriptTemplate.trigger_intent == intent)

    total = len(db.execute(stmt.with_only_columns(ScriptTemplate.id)).scalars().all())
    items = (
        db.execute(
            stmt.order_by(ScriptTemplate.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[_to_out(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/scripts", response_model=ScriptTemplateOut, status_code=201)
def create_provider_script(
    body: ScriptTemplateCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)
    if body.trigger_intent not in VALID_INTENTS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_INVALID_INTENT",
                "message": f"异议类型必须是：{','.join(VALID_INTENTS)}",
            },
        )
    script = ScriptTemplate(
        tenant_id=None,
        provider_id=provider_id,
        title=body.title,
        scene=body.scene,
        trigger_intent=body.trigger_intent,
        content=body.content,
        notes=body.notes,
        version=1,
        created_by=user_id,
    )
    db.add(script)
    db.flush()
    _write_snapshot(db, script, user_id)
    db.commit()
    db.refresh(script)
    return _to_out(script)


@router.patch("/scripts/{script_id}", response_model=ScriptTemplateOut)
def update_provider_script(
    script_id: int,
    body: ScriptTemplateUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)
    script = _get_provider_script(db, script_id, provider_id, for_write=True)

    if body.title is not None:
        script.title = body.title
    if body.scene is not None:
        script.scene = body.scene
    if body.trigger_intent is not None:
        script.trigger_intent = body.trigger_intent
    if body.content is not None:
        script.content = body.content
    if body.notes is not None:
        script.notes = body.notes
    script.version += 1
    _write_snapshot(db, script, user_id)
    db.commit()
    db.refresh(script)
    return _to_out(script)


@router.post("/scripts/{script_id}/toggle", response_model=ScriptTemplateOut)
def toggle_provider_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)
    script = _get_provider_script(db, script_id, provider_id, for_write=True)
    script.is_active = not script.is_active
    db.commit()
    db.refresh(script)
    return _to_out(script)


@router.delete(
    "/scripts/{script_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
def delete_provider_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)
    script = _get_provider_script(db, script_id, provider_id, for_write=True)
    if script.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_STILL_ACTIVE", "message": "请先禁用话术再删除"},
        )
    db.delete(script)
    db.commit()


# v0.7.0 — 服务商话术效果看板(对齐 admin/scripts/effectiveness)
@router.get("/scripts/effectiveness")
def provider_script_effectiveness(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    intent: str | None = Query(None),
    period_days: int = Query(30, ge=1, le=365),
) -> dict:
    """服务商话术效果看板。

    数据范围:本服务商私有话术(`script_template.provider_id == self`)+
    平台预置(`tenant_id IS NULL AND provider_id IS NULL`),与列表 API 一致。

    指标公式与物业侧 `/admin/scripts/effectiveness` 同(详 admin_scripts.py 注释):
      adoption_rate / good_ratio / composite_score / composite_grade /
      ai_score(若已 recompute)
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import case, func

    from app.models.call import CallRecord, SuggestionFeedback

    user_id = int(payload.get("user_id") or 0)
    provider_id = _provider_id_for(db, user_id)
    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    # 本服务商可见话术(provider 私有 + 平台预置)
    template_stmt = select(ScriptTemplate).where(
        or_(
            ScriptTemplate.provider_id == provider_id,
            (ScriptTemplate.tenant_id.is_(None))
            & (ScriptTemplate.provider_id.is_(None)),
        )
    )
    if intent:
        template_stmt = template_stmt.where(ScriptTemplate.trigger_intent == intent)

    templates = db.execute(template_stmt).scalars().all()
    if not templates:
        return {"period_days": period_days, "items": []}

    template_ids = [t.id for t in templates]

    # 聚合反馈(本服务商接的 case 才计入 — 通过 call_record.tenant_id 关联;
    # 简化版:不限 tenant,展示话术总效果。下版本若需限本服务商接案,
    # 需 JOIN CollectionCase → Project.provider_id 过滤。
    feedback_stmt = (
        select(
            SuggestionFeedback.script_template_id,
            func.count().label("total_shown"),
            func.sum(
                case((SuggestionFeedback.action == "adopt", 1), else_=0)
            ).label("total_adopted"),
            func.sum(
                case((SuggestionFeedback.supervisor_label.is_not(None), 1), else_=0)
            ).label("total_supervised"),
            func.sum(
                case((SuggestionFeedback.supervisor_label == "good", 1), else_=0)
            ).label("total_good"),
        )
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(SuggestionFeedback.script_template_id.in_(template_ids))
        .where(SuggestionFeedback.created_at >= cutoff)
        .group_by(SuggestionFeedback.script_template_id)
    )
    agg = {
        r.script_template_id: (
            int(r.total_shown or 0),
            int(r.total_adopted or 0),
            int(r.total_supervised or 0),
            int(r.total_good or 0),
        )
        for r in db.execute(feedback_stmt).all()
    }

    items = []
    for t in templates:
        shown, adopted, supervised, good = agg.get(t.id, (0, 0, 0, 0))
        adoption_rate = adopted / shown if shown else None
        good_ratio = good / supervised if supervised else None

        composite_score: float | None
        if adoption_rate is None and good_ratio is None:
            composite_score = None
        elif good_ratio is None:
            composite_score = adoption_rate
        elif adoption_rate is None:
            composite_score = good_ratio
        else:
            composite_score = 0.6 * adoption_rate + 0.4 * good_ratio

        grade: str | None
        if composite_score is None:
            grade = None
        elif composite_score >= 0.8:
            grade = "A"
        elif composite_score >= 0.6:
            grade = "B"
        elif composite_score >= 0.4:
            grade = "C"
        else:
            grade = "D"

        items.append({
            "template_id": t.id,
            "title": t.title,
            "trigger_intent": t.trigger_intent,
            "is_active": t.is_active,
            "source": (
                "platform" if t.tenant_id is None and t.provider_id is None
                else "provider"
            ),
            "total_shown": shown,
            "total_adopted": adopted,
            "adoption_rate": adoption_rate,
            "total_supervised": supervised,
            "total_good": good,
            "good_ratio": good_ratio,
            "composite_score": composite_score,
            "composite_grade": grade,
            "ai_score": float(t.ai_score) if t.ai_score is not None else None,
            "ai_score_sample_count": t.ai_score_sample_count,
            "ai_score_updated_at": (
                t.ai_score_updated_at.isoformat() if t.ai_score_updated_at else None
            ),
        })
    items.sort(
        key=lambda x: (x["composite_score"] is None, -(x["composite_score"] or 0), -x["total_shown"])
    )
    return {"period_days": period_days, "items": items}
