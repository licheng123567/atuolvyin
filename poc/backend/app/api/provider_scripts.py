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

PROVIDER_ROLES = (
    "admin",
)  # provider-side admin; access guarded by _provider_id_for checking provider_id
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
