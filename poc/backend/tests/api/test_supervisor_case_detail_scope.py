"""Phase 1 补漏 — GET /supervisor/cases/{case_id} scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只能取服务商 A 项目案件详情，取 B / 物业案件 → 404
- 服务商 B 督导只能取服务商 B 项目案件详情，取 A / 物业案件 → 404
- 物业督导只能取物业 / 无项目案件详情，取服务商案件 → 404
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Unique phone counter — 用 151 前缀，避开其他测试文件
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"151{_phone_counter:08d}"


# ---------------------------------------------------------------------------
# Helpers: 造数据
# ---------------------------------------------------------------------------

def _make_provider(db_session, *, name: str) -> object:
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    prov = ServiceProvider(
        name=name,
        provider_type="collection",
        admin_phone_enc=encrypt_phone(_unique_phone()),
    )
    db_session.add(prov)
    db_session.flush()
    return prov


def _make_project(db_session, tenant, *, name: str, provider_id: int | None) -> object:
    from app.models.case import Project

    proj = Project(
        tenant_id=tenant.id,
        name=name,
        provider_id=provider_id,
    )
    db_session.add(proj)
    db_session.flush()
    return proj


def _make_owner(db_session, tenant) -> object:
    from app.core.crypto import encrypt_phone
    from app.models.case import OwnerProfile

    owner = OwnerProfile(
        tenant_id=tenant.id,
        name="业主丙",
        phone_enc=encrypt_phone(_unique_phone()),
        building="3栋",
        room="303",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_case(db_session, tenant, owner, *, project_id: int | None) -> object:
    from app.models.case import CollectionCase

    case = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("1500.00"),
        priority_score=400,
    )
    db_session.add(case)
    db_session.flush()
    return case


def _make_supervisor_token(
    db_session, tenant, *, provider_id: int | None, role: str = "supervisor"
) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导detail",
        phone_enc=encrypt_phone(_unique_phone()),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        provider_id=provider_id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()

    token_payload: dict = {
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": role,
        "scope": f"tenant:{tenant.id}",
    }
    if provider_id is not None:
        token_payload["provider_id"] = provider_id

    return create_access_token(token_payload)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def api(db_session):
    from app.core.db import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as cli:
        yield cli
    app.dependency_overrides.clear()


@pytest.fixture()
def detail_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - case_no_proj：无项目案件（project_id=None）
    - case_property / case_a / case_b：各项目各 1 条案件，各有独立 owner
    - token_property_sv / token_a / token_b：三类督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A-detail")
    provider_b = _make_provider(db_session, name="服务商B-detail")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业自办项目-detail", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-detail", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-detail", provider_id=provider_b.id
    )

    # 各案件需要独立 owner（build_case_detail_response 会查 owner）
    owner_no_proj = _make_owner(db_session, seeded_tenant)
    owner_property = _make_owner(db_session, seeded_tenant)
    owner_a = _make_owner(db_session, seeded_tenant)
    owner_b = _make_owner(db_session, seeded_tenant)

    case_no_proj = _make_case(
        db_session, seeded_tenant, owner_no_proj, project_id=None
    )
    case_property = _make_case(
        db_session, seeded_tenant, owner_property, project_id=proj_property.id
    )
    case_a = _make_case(
        db_session, seeded_tenant, owner_a, project_id=proj_a.id
    )
    case_b = _make_case(
        db_session, seeded_tenant, owner_b, project_id=proj_b.id
    )

    token_property_sv = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=None
    )
    token_a = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=provider_a.id
    )
    token_b = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=provider_b.id
    )

    return SimpleNamespace(
        tenant=seeded_tenant,
        provider_a=provider_a,
        provider_b=provider_b,
        proj_property=proj_property,
        proj_a=proj_a,
        proj_b=proj_b,
        case_no_proj=case_no_proj,
        case_property=case_property,
        case_a=case_a,
        case_b=case_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：服务商 A 督导三向隔离
# ---------------------------------------------------------------------------

def test_provider_a_supervisor_can_get_own_case_detail(api, detail_scope_env):
    """服务商 A 督导取自己项目的案件详情 → 200。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(detail_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == detail_scope_env.case_a.id


def test_provider_a_supervisor_cannot_get_provider_b_case(api, detail_scope_env):
    """服务商 A 督导取服务商 B 项目的案件详情 → 404 ERR_NOT_FOUND。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_b.id}",
        headers=_auth(detail_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_provider_a_supervisor_cannot_get_property_case(api, detail_scope_env):
    """服务商 A 督导取物业自办项目的案件详情 → 404 ERR_NOT_FOUND。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_property.id}",
        headers=_auth(detail_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_provider_a_supervisor_cannot_get_no_project_case(api, detail_scope_env):
    """服务商 A 督导取无项目案件 → 404（无项目案件属于物业侧）。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_no_proj.id}",
        headers=_auth(detail_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


# ---------------------------------------------------------------------------
# 测试 2：服务商 B 督导三向隔离
# ---------------------------------------------------------------------------

def test_provider_b_supervisor_can_get_own_case_detail(api, detail_scope_env):
    """服务商 B 督导取自己项目的案件详情 → 200。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_b.id}",
        headers=_auth(detail_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_b.id


def test_provider_b_supervisor_cannot_get_provider_a_case(api, detail_scope_env):
    """服务商 B 督导取服务商 A 项目的案件详情 → 404。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(detail_scope_env.token_b),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


# ---------------------------------------------------------------------------
# 测试 3：物业督导三向隔离
# ---------------------------------------------------------------------------

def test_property_supervisor_can_get_property_case_detail(api, detail_scope_env):
    """物业督导取物业自办项目的案件详情 → 200。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_property.id}",
        headers=_auth(detail_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_property.id


def test_property_supervisor_can_get_no_project_case_detail(api, detail_scope_env):
    """物业督导取无项目案件详情 → 200（无项目案件属于物业侧）。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_no_proj.id}",
        headers=_auth(detail_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_no_proj.id


def test_property_supervisor_cannot_get_provider_case(api, detail_scope_env):
    """物业督导取服务商 A 项目的案件详情 → 404（跨 scope 隔离）。"""
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(detail_scope_env.token_property_sv),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


# ---------------------------------------------------------------------------
# 测试 4：legal 角色 scope 隔离
# ---------------------------------------------------------------------------

def test_provider_a_legal_can_get_own_case_detail(api, detail_scope_env, db_session):
    """服务商 A legal 取服务商 A 项目的案件详情 → 200（守卫放行 + scope 过滤正确）。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=detail_scope_env.provider_a.id,
        role="legal",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_a.id


def test_provider_a_legal_cannot_get_provider_b_case(api, detail_scope_env, db_session):
    """服务商 A legal 取服务商 B 项目的案件详情 → 404（跨 scope 隔离）。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=detail_scope_env.provider_a.id,
        role="legal",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_b.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_provider_a_legal_cannot_get_property_case(api, detail_scope_env, db_session):
    """服务商 A legal 取物业案件 → 404（跨 scope 隔离）。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=detail_scope_env.provider_a.id,
        role="legal",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_property.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_property_legal_can_get_property_case_detail(api, detail_scope_env, db_session):
    """物业侧 legal 取物业自办项目案件 → 200。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=None,
        role="legal",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_property.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_property.id


def test_property_legal_cannot_get_provider_case(api, detail_scope_env, db_session):
    """物业侧 legal 取服务商 A 案件 → 404（跨 scope 隔离）。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=None,
        role="legal",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def _make_legal_pkg(db_session) -> object:
    """创建一个最小法务服务包（LegalConversionOrder 的 package_id FK 需要）。"""
    from decimal import Decimal

    from app.models.legal_conversion import LegalServicePackage

    pkg = LegalServicePackage(
        tenant_id=None,
        slug="lawyer_letter_det",
        package_type="lawyer_letter",
        name="律师函（详情测试）",
        price=Decimal("199.00"),
        platform_fee_rate=Decimal("0.30"),
        sort_order=99,
    )
    db_session.add(pkg)
    db_session.flush()
    return pkg


def test_property_legal_force_phone_reveal_with_internal_processing_order(
    api, detail_scope_env, db_session
):
    """物业侧 legal 访问有 internal_processing 法务订单的案件 → 200 且电话明文。

    force_phone_reveal 路径：legal 角色 + 订单 status='internal_processing'
    → build_case_detail_response 收到 force_owner_phone_reveal=True
    → phone_masked 字段返回明文（非 138****XXXX 格式）。
    """
    from app.models.legal_conversion import LegalConversionOrder

    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=None,
        role="legal",
    )
    pkg = _make_legal_pkg(db_session)
    order = LegalConversionOrder(
        tenant_id=detail_scope_env.tenant.id,
        case_id=detail_scope_env.case_property.id,
        package_id=pkg.id,
        status="internal_processing",
        price_quoted=__import__("decimal").Decimal("199.00"),
        platform_fee_amount=__import__("decimal").Decimal("59.70"),
    )
    db_session.add(order)
    db_session.flush()

    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_property.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 明文手机号不含 "****"（脱敏格式为 138****1234）
    phone_masked = data["owner"]["phone_masked"]
    assert "****" not in phone_masked, (
        f"期望明文手机号，实际为脱敏格式：{phone_masked!r}"
    )


# ---------------------------------------------------------------------------
# 测试 5：coordinator 角色守卫放行
# ---------------------------------------------------------------------------

def test_provider_a_coordinator_can_get_own_case_detail(api, detail_scope_env, db_session):
    """服务商 A coordinator 取自己项目的案件详情 → 200（守卫放行确认）。"""
    token = _make_supervisor_token(
        db_session, detail_scope_env.tenant,
        provider_id=detail_scope_env.provider_a.id,
        role="coordinator",
    )
    resp = api.get(
        f"/api/v1/supervisor/cases/{detail_scope_env.case_a.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == detail_scope_env.case_a.id
