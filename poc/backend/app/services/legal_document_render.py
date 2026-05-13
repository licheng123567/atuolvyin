"""Sprint 16.4 — 法律文书 mustache-style 渲染 (PRD §20.4)。

只支持 {{var_name}} 占位符替换，未填占位符回落 [未填]。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import CollectionCase, OwnerProfile
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.models.legal_document_template import LegalDocumentTemplate
from app.models.tenant import Tenant

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_template_body(body_md: str, ctx: dict[str, Any]) -> str:
    """以 {{name}} 替换 ctx 中对应值；缺省时填 [未填]。"""

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in ctx and ctx[key] is not None and ctx[key] != "":
            return str(ctx[key])
        return "[未填]"

    return _VAR_RE.sub(_sub, body_md)


def build_order_render_context(db: Session, *, order: LegalConversionOrder) -> dict[str, Any]:
    """从一个 conversion_order 聚合渲染所需的所有变量。"""
    ctx: dict[str, Any] = {
        "today_date": datetime.now(UTC).strftime("%Y-%m-%d"),
    }

    # tenant
    tenant = db.get(Tenant, order.tenant_id)
    ctx["tenant_name"] = tenant.name if tenant else None

    # case + owner
    case = db.get(CollectionCase, order.case_id)
    if case is not None:
        ctx["amount_owed"] = f"{float(case.amount_owed):,.2f}" if case.amount_owed else "0.00"
        ctx["months_overdue"] = case.months_overdue or 0
        owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
        if owner is not None:
            ctx["owner_name"] = owner.name
            building = (owner.building or "").strip()
            room = (owner.room or "").strip()
            ctx["owner_address"] = f"{building} {room}".strip() if (building or room) else "[未填]"

    # firm + lawyer
    if order.law_firm_id is not None:
        firm = db.get(LawFirm, order.law_firm_id)
        ctx["firm_name"] = firm.name if firm else order.assigned_law_firm
    else:
        ctx["firm_name"] = order.assigned_law_firm
    if order.lawyer_id is not None:
        lawyer = db.get(LawFirmLawyer, order.lawyer_id)
        ctx["lawyer_name"] = lawyer.name if lawyer else order.assigned_lawyer_name
    else:
        ctx["lawyer_name"] = order.assigned_lawyer_name

    # 通话历史 — 从 timeline_summary 取（订单创建时已冻结）
    if order.timeline_summary:
        ctx["total_calls"] = order.timeline_summary.get("total_calls", 0)
    else:
        ctx["total_calls"] = 0

    return ctx


def get_template_for_order(
    db: Session, *, order: LegalConversionOrder
) -> LegalDocumentTemplate | None:
    """按 (tenant_id, package_type) 找模板：先租户级覆盖，否则平台默认。"""
    package = db.get(LegalServicePackage, order.package_id)
    if package is None:
        return None
    pkg_type = package.package_type

    tenant_tpl = db.execute(
        select(LegalDocumentTemplate)
        .where(
            LegalDocumentTemplate.package_type == pkg_type,
            LegalDocumentTemplate.tenant_id == order.tenant_id,
            LegalDocumentTemplate.enabled.is_(True),
        )
        .order_by(LegalDocumentTemplate.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if tenant_tpl is not None:
        return tenant_tpl

    return db.execute(
        select(LegalDocumentTemplate)
        .where(
            LegalDocumentTemplate.package_type == pkg_type,
            LegalDocumentTemplate.tenant_id.is_(None),
            LegalDocumentTemplate.enabled.is_(True),
        )
        .order_by(LegalDocumentTemplate.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def render_for_order(db: Session, *, order: LegalConversionOrder, rendered_by: int | None = None):
    """生成新版本的 LegalDocumentRender；返回 ORM 对象，调用方 commit。"""
    from app.models.legal_document_template import LegalDocumentRender

    tpl = get_template_for_order(db, order=order)
    if tpl is None:
        raise ValueError("no template available for this package_type")

    ctx = build_order_render_context(db, order=order)
    rendered_body = render_template_body(tpl.body_md, ctx)

    # next version
    last_version = db.execute(
        select(LegalDocumentRender.version)
        .where(LegalDocumentRender.order_id == order.id)
        .order_by(LegalDocumentRender.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_version = (last_version or 0) + 1

    render = LegalDocumentRender(
        order_id=order.id,
        template_id=tpl.id,
        title=tpl.title,
        body_md=rendered_body,
        rendered_by=rendered_by,
        version=next_version,
    )
    db.add(render)
    db.flush()
    return render
