"""§9.1 — LegalConversionRequestMaterial 模型 round-trip 测试。"""
from __future__ import annotations


def test_legal_conversion_request_material_round_trip(
    db_session, seeded_tenant, seeded_case, seeded_member_user
):
    from app.models.legal_conversion import (
        LegalConversionRequest,
        LegalConversionRequestMaterial,
    )

    req = LegalConversionRequest(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        requester_user_id=seeded_member_user.id,
        requester_role="legal",
        status="pending",
    )
    db_session.add(req)
    db_session.flush()

    mat = LegalConversionRequestMaterial(
        request_id=req.id,
        tenant_id=seeded_tenant.id,
        object_key="legal_conv_req_materials/1/1/abc.pdf",
        filename="证据材料.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        uploaded_by=seeded_member_user.id,
    )
    db_session.add(mat)
    db_session.flush()
    db_session.refresh(mat)

    got = db_session.get(LegalConversionRequestMaterial, mat.id)
    assert got is not None
    assert got.request_id == req.id
    assert got.tenant_id == seeded_tenant.id
    assert got.filename == "证据材料.pdf"
    assert got.content_type == "application/pdf"
    assert got.size_bytes == 2048
    assert got.uploaded_by == seeded_member_user.id
    assert got.created_at is not None
