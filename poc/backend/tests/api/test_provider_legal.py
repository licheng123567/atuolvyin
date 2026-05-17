"""§9.1 — 服务商法务端点测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient


def _seed_provider_env(db_session, tenant, *, provider_name, owner_phone, project_status="active"):
    """建 provider + project(provider_id) + owner + case + provider-legal 用户 + token。

    返回 SimpleNamespace(provider, project, owner, case, user, token)。
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.case import CollectionCase, OwnerProfile, Project
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name=provider_name,
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900000000"),
    )
    db_session.add(provider)
    db_session.flush()

    project = Project(
        tenant_id=tenant.id,
        name=f"{provider_name}-项目",
        provider_id=provider.id,
        status=project_status,
        plan_end=datetime.now(UTC) + timedelta(days=90),
    )
    db_session.add(project)
    db_session.flush()

    owner = OwnerProfile(
        tenant_id=tenant.id,
        name="业主测试",
        phone_enc=encrypt_phone(owner_phone),
        building="2栋",
        room="202",
    )
    db_session.add(owner)
    db_session.flush()

    case = CollectionCase(
        tenant_id=tenant.id,
        project_id=project.id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("5000.00"),
        months_overdue=4,
        priority_score=900,
    )
    db_session.add(case)
    db_session.flush()

    user = UserAccount(
        name=f"{provider_name}-法务",
        phone_enc=encrypt_phone(owner_phone),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role="legal",
        provider_id=provider.id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()

    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "legal",
        "provider_id": provider.id,
        "scope": f"tenant:{tenant.id}",
    })
    return SimpleNamespace(
        provider=provider, project=project, owner=owner, case=case, user=user, token=token
    )


@pytest.fixture
def api(db_session):
    from app.core.db import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as cli:
        yield cli
    app.dependency_overrides.clear()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_list_cases_rejects_property_side_legal(api, db_session, seeded_tenant):
    """物业侧 legal（provider_id 空）访问 /provider/legal/* → 403。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    u = UserAccount(name="物业法务", phone_enc=encrypt_phone("13700000001"),
                    password_hash=get_password_hash("pw"), is_active=True)
    db_session.add(u)
    db_session.flush()
    db_session.add(UserTenantMembership(
        tenant_id=seeded_tenant.id, user_id=u.id, role="legal", is_active=True))
    db_session.flush()
    token = create_access_token({
        "sub": str(u.id), "user_id": u.id, "tenant_id": seeded_tenant.id,
        "role": "legal", "scope": f"tenant:{seeded_tenant.id}",
    })
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(token))
    assert resp.status_code == 403


def test_list_cases_returns_own_provider_cases(api, db_session, seeded_tenant):
    """服务商法务只看到本服务商项目下的案件。"""
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["case_id"] == env.case.id
    assert item["project_id"] == env.project.id
    # 电话脱敏
    assert item["owner_phone_masked"] == "137****5678"


def test_list_cases_cross_provider_isolation(api, db_session, seeded_tenant):
    """服务商A 的法务看不到服务商B 的案件。"""
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    _seed_provider_env(db_session, seeded_tenant,
                       provider_name="服务商B", owner_phone="13755556666")
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(env_a.token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["case_id"] == env_a.case.id


def test_get_case_detail(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.get(f"/api/v1/provider/legal/cases/{env.case.id}", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_id"] == env.case.id
    assert body["owner_phone_masked"] == "137****5678"
    assert body["stage"] == "new"
    assert body["call_count"] == 0


def test_get_case_detail_cross_provider_404(api, db_session, seeded_tenant):
    """服务商A 的法务取服务商B 的案件 → 404。"""
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    resp = api.get(f"/api/v1/provider/legal/cases/{env_b.case.id}", headers=_auth(env_a.token))
    assert resp.status_code == 404


def test_list_cases_rejects_provider_side_non_legal(api, db_session, seeded_tenant):
    """服务商侧非 legal 角色（如服务商催收员）访问 /provider/legal/* → 403。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="服务商X", provider_type="collection",
        admin_phone_enc=encrypt_phone("13900000099"),
    )
    db_session.add(provider)
    db_session.flush()
    u = UserAccount(
        name="服务商催收员", phone_enc=encrypt_phone("13700000099"),
        password_hash=get_password_hash("pw"), is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    db_session.add(UserTenantMembership(
        tenant_id=seeded_tenant.id, user_id=u.id, role="agent",
        provider_id=provider.id, work_mode="external", is_active=True,
    ))
    db_session.flush()
    token = create_access_token({
        "sub": str(u.id), "user_id": u.id, "tenant_id": seeded_tenant.id,
        "role": "agent", "provider_id": provider.id,
        "scope": f"tenant:{seeded_tenant.id}",
    })
    resp = api.get("/api/v1/provider/legal/cases", headers=_auth(token))
    assert resp.status_code == 403


def test_create_conversion_request(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "业主长期拒缴，建议走法务"},
        headers=_auth(env.token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == env.case.id
    assert body["status"] == "pending"
    assert body["reason"] == "业主长期拒缴，建议走法务"
    assert body["order_status"] is None

    from app.models.legal_conversion import LegalConversionRequest
    req = db_session.get(LegalConversionRequest, body["id"])
    assert req is not None
    assert req.requester_role == "legal"
    assert req.requester_user_id == env.user.id


def test_create_conversion_request_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env_b.case.id}/conversion-request",
        json={"reason": "x"},
        headers=_auth(env_a.token),
    )
    assert resp.status_code == 404


def test_create_conversion_request_duplicate_pending_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    first = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "第一次"}, headers=_auth(env.token),
    )
    assert first.status_code == 201
    second = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "第二次"}, headers=_auth(env.token),
    )
    assert second.status_code == 409
    assert second.json()["code"] == "ERR_REQUEST_PENDING"


def test_create_conversion_request_active_order_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    from decimal import Decimal

    from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
    pkg = LegalServicePackage(
        tenant_id=None, slug="lawyer_letter", package_type="lawyer_letter",
        name="律师函", price=Decimal("199.00"), platform_fee_rate=Decimal("0.30"),
    )
    db_session.add(pkg)
    db_session.flush()
    order = LegalConversionOrder(
        tenant_id=seeded_tenant.id, case_id=env.case.id, status="in_service",
        package_id=pkg.id, price_quoted=Decimal("199.00"),
        platform_fee_amount=Decimal("59.70"),
    )
    db_session.add(order)
    db_session.flush()
    resp = api.post(
        f"/api/v1/provider/legal/cases/{env.case.id}/conversion-request",
        json={"reason": "x"}, headers=_auth(env.token),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_LEGAL_ORDER_EXISTS"


def _create_request(db_session, env):
    """直接建一个 pending 的 LegalConversionRequest，返回它。"""
    from app.models.legal_conversion import LegalConversionRequest
    req = LegalConversionRequest(
        tenant_id=env.case.tenant_id, case_id=env.case.id,
        requester_user_id=env.user.id, requester_role="legal", status="pending",
    )
    db_session.add(req)
    db_session.flush()
    return req


def test_upload_and_download_material(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    up = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=_auth(env.token),
    )
    assert up.status_code == 201, up.text
    mat = up.json()
    assert mat["request_id"] == req.id
    assert mat["filename"] == "证据.pdf"
    assert mat["size_bytes"] == len(b"%PDF-1.4 fake")

    dl = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials/{mat['id']}",
        headers=_auth(env.token),
    )
    assert dl.status_code == 200, dl.text
    assert dl.json()["download_url"]
    assert dl.json()["filename"] == "证据.pdf"


def test_upload_material_empty_file_422(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=_auth(env.token),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_EMPTY_FILE"


def test_upload_material_non_pending_409(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    req.status = "approved"
    db_session.flush()
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4", "application/pdf")},
        headers=_auth(env.token),
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_REQUEST_NOT_PENDING"


def test_upload_material_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    req_b = _create_request(db_session, env_b)
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4", "application/pdf")},
        headers=_auth(env_a.token),
    )
    assert resp.status_code == 404


def test_download_material_cross_provider_404(api, db_session, seeded_tenant):
    """服务商A 不能下载服务商B 请求下的材料。"""
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    req_b = _create_request(db_session, env_b)
    up = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4", "application/pdf")},
        headers=_auth(env_b.token),
    )
    assert up.status_code == 201
    mat_id = up.json()["id"]
    resp = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}/materials/{mat_id}",
        headers=_auth(env_a.token),
    )
    assert resp.status_code == 404


def test_upload_material_invalid_mime_422(api, db_session, seeded_tenant):
    """不允许的 MIME 类型 → 422 ERR_INVALID_MIME。"""
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    resp = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("bad.exe", b"MZ\x90\x00", "application/x-msdownload")},
        headers=_auth(env.token),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_INVALID_MIME"


def test_list_conversion_requests(api, db_session, seeded_tenant):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    resp = api.get("/api/v1/provider/legal/conversion-requests", headers=_auth(env.token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == req.id
    assert body["items"][0]["status"] == "pending"


def test_list_conversion_requests_cross_provider_isolation(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    _create_request(db_session, env_a)
    _create_request(db_session, env_b)
    resp = api.get("/api/v1/provider/legal/conversion-requests", headers=_auth(env_a.token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_conversion_request_detail_with_materials_and_order_status(
    api, db_session, seeded_tenant
):
    env = _seed_provider_env(db_session, seeded_tenant,
                             provider_name="服务商A", owner_phone="13712345678")
    req = _create_request(db_session, env)
    from decimal import Decimal

    from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
    pkg = LegalServicePackage(
        tenant_id=None, slug="lawyer_letter_detail", package_type="lawyer_letter",
        name="律师函", price=Decimal("199.00"), platform_fee_rate=Decimal("0.30"),
    )
    db_session.add(pkg)
    db_session.flush()
    order = LegalConversionOrder(
        tenant_id=seeded_tenant.id, case_id=env.case.id, status="internal_processing",
        package_id=pkg.id, price_quoted=Decimal("199.00"),
        platform_fee_amount=Decimal("59.70"),
    )
    db_session.add(order)
    db_session.flush()
    req.related_order_id = order.id
    db_session.flush()
    up = api.post(
        f"/api/v1/provider/legal/conversion-requests/{req.id}/materials",
        files={"file": ("证据.pdf", b"%PDF-1.4 x", "application/pdf")},
        headers=_auth(env.token),
    )
    assert up.status_code == 201

    resp = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req.id}", headers=_auth(env.token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == req.id
    assert body["order_status"] == "internal_processing"
    assert len(body["materials"]) == 1
    assert body["materials"][0]["filename"] == "证据.pdf"


def test_get_conversion_request_detail_cross_provider_404(api, db_session, seeded_tenant):
    env_a = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商A", owner_phone="13712345678")
    env_b = _seed_provider_env(db_session, seeded_tenant,
                               provider_name="服务商B", owner_phone="13755556666")
    req_b = _create_request(db_session, env_b)
    resp = api.get(
        f"/api/v1/provider/legal/conversion-requests/{req_b.id}", headers=_auth(env_a.token)
    )
    assert resp.status_code == 404
