from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.script import ScriptTemplate, ScriptTemplateVersion
from app.schemas.script import (
    RollbackIn, ScriptTemplateCreate,
    ScriptTemplateOut, ScriptTemplateUpdate, ScriptVersionOut,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")


def _write_snapshot(db: Session, script: ScriptTemplate, editor_id: int) -> None:
    v = ScriptTemplateVersion(
        script_template_id=script.id,
        version=script.version,
        title=script.title,
        trigger_intent=script.trigger_intent,
        content=script.content,
        notes=script.notes,
        edited_by=editor_id,
    )
    db.add(v)


def _get_script_or_404(db: Session, script_id: int, role: str, tenant_id: int) -> ScriptTemplate:
    stmt = select(ScriptTemplate).where(ScriptTemplate.id == script_id)
    if role != "platform_superadmin":
        stmt = stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
    script = db.execute(stmt).scalar_one_or_none()
    if not script:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "话术不存在"},
        )
    return script


@router.get("/scripts", response_model=PaginatedResponse[ScriptTemplateOut])
def list_scripts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ScriptTemplateOut]:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)

    stmt = select(ScriptTemplate)
    if role != "platform_superadmin":
        stmt = stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
    if q:
        stmt = stmt.where(
            or_(ScriptTemplate.title.ilike(f"%{q}%"), ScriptTemplate.content.ilike(f"%{q}%"))
        )
    if intent:
        stmt = stmt.where(ScriptTemplate.trigger_intent == intent)
    if status == "active":
        stmt = stmt.where(ScriptTemplate.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(ScriptTemplate.is_active.is_(False))

    total_ids = db.execute(stmt.with_only_columns(ScriptTemplate.id)).scalars().all()
    items = db.execute(
        stmt.order_by(ScriptTemplate.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return PaginatedResponse(items=list(items), total=len(total_ids), page=page, page_size=page_size)


@router.post("/scripts", response_model=ScriptTemplateOut, status_code=201)
def create_script(
    body: ScriptTemplateCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = ScriptTemplate(
        tenant_id=None if role == "platform_superadmin" else tenant_id,
        title=body.title,
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
    return script


@router.patch("/scripts/{script_id}", response_model=ScriptTemplateOut)
def update_script(
    script_id: int,
    body: ScriptTemplateUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = _get_script_or_404(db, script_id, role, tenant_id)

    if body.title is not None:
        script.title = body.title
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
    return script


@router.post("/scripts/{script_id}/toggle", response_model=ScriptTemplateOut)
def toggle_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id)
    script.is_active = not script.is_active
    db.commit()
    db.refresh(script)
    return script


@router.delete("/scripts/{script_id}", status_code=204)
def delete_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id)
    if script.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_STILL_ACTIVE", "message": "请先禁用话术再删除"},
        )
    db.delete(script)
    db.commit()


@router.get("/scripts/{script_id}/versions", response_model=list[ScriptVersionOut])
def get_versions(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScriptVersionOut]:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    _get_script_or_404(db, script_id, role, tenant_id)
    versions = db.execute(
        select(ScriptTemplateVersion)
        .where(ScriptTemplateVersion.script_template_id == script_id)
        .order_by(ScriptTemplateVersion.version.desc())
    ).scalars().all()
    return list(versions)


@router.post("/scripts/{script_id}/rollback", response_model=ScriptTemplateOut)
def rollback_script(
    script_id: int,
    body: RollbackIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = _get_script_or_404(db, script_id, role, tenant_id)
    target = db.execute(
        select(ScriptTemplateVersion).where(
            ScriptTemplateVersion.script_template_id == script_id,
            ScriptTemplateVersion.version == body.to_version,
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": f"版本 {body.to_version} 不存在"},
        )

    script.title = target.title
    script.trigger_intent = target.trigger_intent
    script.content = target.content
    script.notes = target.notes
    script.version += 1
    _write_snapshot(db, script, user_id)

    db.commit()
    db.refresh(script)
    return script
