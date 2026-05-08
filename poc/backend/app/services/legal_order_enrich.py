"""v1.6 — LegalConversionOrder 富化 helper：joins case/owner/project/tenant/docs。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.models.legal_document import LegalDocument
from app.models.tenant import Tenant
from app.models.user import UserAccount

PACKAGE_LABELS: dict[str, str] = {
    "lawyer_letter": "律师函",
    "mediation": "诉前调解",
    "small_claims": "小额诉讼",
    "full_agency": "完整代理",
}

DOC_TYPE_LABELS: dict[str, str] = {
    "lawyer_letter": "律师函",
    "mediation_record": "调解记录",
    "court_filing": "立案材料",
    "judgment": "判决书",
    "other": "其他文书",
}


def enrich_order(db: Session, order: LegalConversionOrder) -> dict:
    """把 LegalConversionOrder 转成前端期望的扁平 dict（含 case / owner / project / tenant / docs）。"""
    case = db.get(CollectionCase, order.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
    project = db.get(Project, case.project_id) if case and case.project_id else None
    tenant = db.get(Tenant, order.tenant_id)
    package = db.get(LegalServicePackage, order.package_id)
    firm = db.get(LawFirm, order.law_firm_id) if order.law_firm_id else None
    lawyer = db.get(LawFirmLawyer, order.lawyer_id) if order.lawyer_id else None
    creator = db.get(UserAccount, order.created_by) if order.created_by else None

    docs_rows = db.execute(
        select(LegalDocument)
        .where(LegalDocument.case_id == order.case_id)
        .order_by(LegalDocument.id)
    ).scalars().all()
    docs = []
    for d in docs_rows:
        uploader = db.get(UserAccount, d.uploaded_by) if d.uploaded_by else None
        docs.append({
            "id": d.id,
            "doc_type": d.doc_type,
            "doc_label": DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
            "filename": d.filename,
            "uploaded_by": uploader.name if uploader else None,
            "uploaded_at": d.created_at.isoformat() if d.created_at else None,
            "url": f"/api/v1/legal-documents/{d.id}/download",
        })

    package_type = package.package_type if package else None
    package_label = (
        PACKAGE_LABELS.get(package_type, package.name)
        if package and package_type
        else (package.name if package else "—")
    )

    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "tenant_name": tenant.name if tenant else None,
        "case_id": order.case_id,
        "case_owner": owner.name if owner else None,
        "case_building": (owner.building or "") if owner else None,
        "case_amount": float(case.amount_owed) if case and case.amount_owed is not None else None,
        "case_months_overdue": case.months_overdue if case else None,
        "project_name": project.name if project else None,
        "package_id": order.package_id,
        "package": package_type,
        "package_label": package_label,
        "status": order.status,
        "price_quoted": float(order.price_quoted),
        "platform_fee_amount": float(order.platform_fee_amount),
        "law_firm_id": order.law_firm_id,
        "law_firm_name": firm.name if firm else order.assigned_law_firm,
        "lawyer_id": order.lawyer_id,
        "lawyer_name": lawyer.name if lawyer else order.assigned_lawyer_name,
        "created_by": creator.name if creator else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "dispatched_at": order.dispatched_at.isoformat() if order.dispatched_at else None,
        "in_service_at": None,  # 当前 LegalConversionOrder 无此字段，留空
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "notes": order.notes,
        "timeline_summary": (
            order.timeline_summary.get("text")
            if isinstance(order.timeline_summary, dict)
            else (str(order.timeline_summary) if order.timeline_summary else None)
        ),
        "docs": docs,
    }
