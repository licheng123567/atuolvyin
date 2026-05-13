from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi import status as http_status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord, SuggestionFeedback
from app.models.script import ScriptTemplate, ScriptTemplateVersion
from app.schemas.common import PaginatedResponse
from app.schemas.script import (
    ImportResultOut,
    RollbackIn,
    ScriptEffectivenessItem,
    ScriptEffectivenessOut,
    ScriptTemplateCreate,
    ScriptTemplateOut,
    ScriptTemplateUpdate,
    ScriptVersionOut,
)

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")

VALID_INTENTS = frozenset({"房屋质量", "经济困难", "服务不满", "联系困难", "其他"})


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


def _script_source(script: ScriptTemplate) -> str:
    """Compute three-layer source label for ScriptTemplate."""
    if script.provider_id is not None:
        return "provider"
    if script.tenant_id is not None:
        return "tenant"
    return "platform"


def _to_out(script: ScriptTemplate, project_name: str | None = None) -> ScriptTemplateOut:
    return ScriptTemplateOut.model_validate(
        {
            **{c.name: getattr(script, c.name) for c in script.__table__.columns},
            "source": _script_source(script),
            "project_name": project_name,
        }
    )


def _enrich_with_project(db: Session, script: ScriptTemplate) -> ScriptTemplateOut:
    project_name: str | None = None
    if script.project_id:
        from app.models.case import Project

        project_name = db.execute(
            select(Project.name).where(Project.id == script.project_id)
        ).scalar_one_or_none()
    return _to_out(script, project_name)


def _get_script_or_404(
    db: Session,
    script_id: int,
    role: str,
    tenant_id: int,
    *,
    for_write: bool = False,
) -> ScriptTemplate:
    """Load script. Read 可见平台 + 本租户私有；写仅限本租户私有（admin）。

    v1.4 S16.5：屏蔽 admin 改/删平台预置（之前是 bug）。
    platform_superadmin 仍可改平台预置。
    """
    stmt = select(ScriptTemplate).where(ScriptTemplate.id == script_id)
    if role != "platform_superadmin":
        stmt = stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
        # admin 永远不可见服务商私有话术
        stmt = stmt.where(ScriptTemplate.provider_id.is_(None))
    script = db.execute(stmt).scalar_one_or_none()
    if not script:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "话术不存在"},
        )
    if for_write and role != "platform_superadmin" and script.tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_PLATFORM_READONLY",
                "message": "平台预置话术不可直接修改，请先 Fork 为本物业版",
            },
        )
    return script


@router.get("/scripts", response_model=PaginatedResponse[ScriptTemplateOut])
def list_scripts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None),
    intent: str | None = Query(None),
    status: str | None = Query(None),
    project_id: int | None = Query(None),
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
        # v1.4 S16.5 — admin 列表永远不可见服务商私有话术
        stmt = stmt.where(ScriptTemplate.provider_id.is_(None))
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
    # v1.5.7 — 项目级过滤：传 project_id=N 时返回「全项目通用 + 该项目专属」
    if project_id is not None:
        stmt = stmt.where(
            or_(ScriptTemplate.project_id.is_(None), ScriptTemplate.project_id == project_id)
        )

    total_ids = db.execute(stmt.with_only_columns(ScriptTemplate.id)).scalars().all()
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
        items=[_enrich_with_project(db, s) for s in items],
        total=len(total_ids),
        page=page,
        page_size=page_size,
    )


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

    # v1.5.7 — 校验 project_id 属本租户
    project_id_to_set: int | None = None
    if body.project_id is not None and role != "platform_superadmin":
        from app.models.case import Project

        ok = db.execute(
            select(Project.id).where(Project.id == body.project_id, Project.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if ok is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_INVALID_PROJECT", "message": "项目不存在或不属本租户"},
            )
        project_id_to_set = body.project_id

    script = ScriptTemplate(
        tenant_id=None if role == "platform_superadmin" else tenant_id,
        project_id=project_id_to_set,
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
    return _enrich_with_project(db, script)


@router.post("/scripts/import", response_model=ImportResultOut)
def import_scripts(
    file: Annotated[UploadFile, File(...)],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ImportResultOut:
    import openpyxl

    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0) if role != "platform_superadmin" else None
    user_id = int(payload.get("user_id") or 0)

    contents = file.file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_INVALID_FILE", "message": "无法解析 Excel 文件"},
        ) from exc

    ws = wb.active
    tenant_filter = (
        or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        if tenant_id is not None
        else ScriptTemplate.tenant_id.is_(None)
    )
    existing_titles = {
        row[0] for row in db.execute(select(ScriptTemplate.title).where(tenant_filter)).all()
    }

    success = skipped = failed = 0
    errors: list[str] = []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        title, intent, content, notes = (row[j] if j < len(row) else None for j in range(4))
        title = str(title).strip() if title else ""
        intent = str(intent).strip() if intent else ""
        content = str(content).strip() if content else ""
        notes = str(notes).strip() if notes else None

        if not title or not intent or not content:
            if len(errors) < 10:
                errors.append(f"第 {i} 行：标题/异议类型/内容不能为空")
            failed += 1
            continue
        if intent not in VALID_INTENTS:
            if len(errors) < 10:
                errors.append(f"第 {i} 行：异议类型「{intent}」不在枚举范围内")
            failed += 1
            continue
        if title in existing_titles:
            skipped += 1
            continue

        script = ScriptTemplate(
            tenant_id=tenant_id,
            title=title,
            trigger_intent=intent,
            content=content,
            notes=notes or None,
            version=1,
            created_by=user_id,
        )
        db.add(script)
        db.flush()
        _write_snapshot(db, script, user_id)
        existing_titles.add(title)
        success += 1

    db.commit()
    return ImportResultOut(success=success, skipped=skipped, failed=failed, errors=errors)


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

    script = _get_script_or_404(db, script_id, role, tenant_id, for_write=True)

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
    # v1.5.7 — 项目级范围可改：明确传 project_id（含 null）即更新
    if "project_id" in body.model_fields_set:
        if body.project_id is not None and role != "platform_superadmin":
            from app.models.case import Project

            ok = db.execute(
                select(Project.id).where(
                    Project.id == body.project_id, Project.tenant_id == tenant_id
                )
            ).scalar_one_or_none()
            if ok is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail={"code": "ERR_INVALID_PROJECT", "message": "项目不存在或不属本租户"},
                )
        script.project_id = body.project_id
    script.version += 1
    _write_snapshot(db, script, user_id)

    db.commit()
    db.refresh(script)
    return _enrich_with_project(db, script)


@router.post("/scripts/{script_id}/fork", response_model=ScriptTemplateOut, status_code=201)
def fork_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    """v1.4 S16.5 — admin 把平台预置话术 fork 成本租户私有副本。"""
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    if role == "platform_superadmin":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_NOT_APPLICABLE", "message": "超管直接编辑平台预置即可"},
        )

    src = _get_script_or_404(db, script_id, role, tenant_id, for_write=False)
    if src.tenant_id is not None or src.provider_id is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_NOT_PLATFORM", "message": "仅平台预置话术可 Fork"},
        )

    clone = ScriptTemplate(
        tenant_id=tenant_id,
        provider_id=None,
        title=src.title,
        trigger_intent=src.trigger_intent,
        content=src.content,
        notes=src.notes,
        version=1,
        created_by=user_id,
    )
    db.add(clone)
    db.flush()
    _write_snapshot(db, clone, user_id)
    db.commit()
    db.refresh(clone)
    return _to_out(clone)


@router.post("/scripts/{script_id}/toggle", response_model=ScriptTemplateOut)
def toggle_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id, for_write=True)
    was_active = script.is_active
    script.is_active = not script.is_active
    db.commit()
    db.refresh(script)
    # Sprint 15.4b — script_disabled 通知（仅 active→inactive 时触发；租户级话术才发）
    if was_active and not script.is_active and script.tenant_id is not None:
        from app.services.notifications.event_subscribers import notify_script_disabled

        notify_script_disabled(
            db,
            tenant_id=int(script.tenant_id),
            script_id=int(script.id),
            script_name=script.title,
            operator_user_id=int(payload.get("user_id") or 0) or None,
        )
        db.commit()
    return _to_out(script)


@router.delete(
    "/scripts/{script_id}", status_code=204, response_class=Response, response_model=None
)
def delete_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id, for_write=True)
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
    versions = (
        db.execute(
            select(ScriptTemplateVersion)
            .where(ScriptTemplateVersion.script_template_id == script_id)
            .order_by(ScriptTemplateVersion.version.desc())
        )
        .scalars()
        .all()
    )
    return list(versions)


@router.get("/scripts/effectiveness", response_model=ScriptEffectivenessOut)
def script_effectiveness(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    intent: str | None = Query(None),
    period_days: int = Query(30, ge=1, le=365),
) -> ScriptEffectivenessOut:
    """采用率 / 督导好评率 / 综合评分（A-D 四级）— 按 trigger_intent 可筛。

    采用率 = adopt / (adopt + ignore)
    好评率 = good / (good + bad)（仅计入有督导标注的反馈）
    综合得分 = 0.6 * adoption_rate + 0.4 * good_ratio（无督导标注则跳过该项权重）
    评级阈值：>=0.8 A，>=0.6 B，>=0.4 C，<0.4 D
    """
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)

    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    template_stmt = select(ScriptTemplate)
    if role != "platform_superadmin":
        template_stmt = template_stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
    if intent:
        template_stmt = template_stmt.where(ScriptTemplate.trigger_intent == intent)

    templates = db.execute(template_stmt).scalars().all()
    if not templates:
        return ScriptEffectivenessOut(period_days=period_days, items=[])

    template_ids = [t.id for t in templates]

    feedback_stmt = (
        select(
            SuggestionFeedback.script_template_id,
            func.count().label("total_shown"),
            func.sum(case((SuggestionFeedback.action == "adopt", 1), else_=0)).label(
                "total_adopted"
            ),
            func.sum(case((SuggestionFeedback.supervisor_label.is_not(None), 1), else_=0)).label(
                "total_supervised"
            ),
            func.sum(case((SuggestionFeedback.supervisor_label == "good", 1), else_=0)).label(
                "total_good"
            ),
        )
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(SuggestionFeedback.script_template_id.in_(template_ids))
        .where(SuggestionFeedback.created_at >= cutoff)
        .group_by(SuggestionFeedback.script_template_id)
    )
    if role != "platform_superadmin":
        feedback_stmt = feedback_stmt.where(CallRecord.tenant_id == tenant_id)

    agg: dict[int, tuple[int, int, int, int]] = {
        row.script_template_id: (
            int(row.total_shown or 0),
            int(row.total_adopted or 0),
            int(row.total_supervised or 0),
            int(row.total_good or 0),
        )
        for row in db.execute(feedback_stmt).all()
    }

    items: list[ScriptEffectivenessItem] = []
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

        items.append(
            ScriptEffectivenessItem(
                template_id=t.id,
                title=t.title,
                trigger_intent=t.trigger_intent,
                is_active=t.is_active,
                total_shown=shown,
                total_adopted=adopted,
                adoption_rate=adoption_rate,
                total_supervised=supervised,
                total_good=good,
                good_ratio=good_ratio,
                composite_score=composite_score,
                composite_grade=grade,  # type: ignore[arg-type]
            )
        )

    items.sort(key=lambda x: (x.composite_score is None, -(x.composite_score or 0), -x.total_shown))
    return ScriptEffectivenessOut(period_days=period_days, items=items)


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

    script = _get_script_or_404(db, script_id, role, tenant_id, for_write=True)
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
    return _to_out(script)
