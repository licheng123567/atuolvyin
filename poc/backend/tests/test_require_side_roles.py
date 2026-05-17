"""Task 5b — 越权守卫依赖单元测试。

require_tenant_roles / require_provider_roles 各自验证两层:
1. 角色名匹配
2. provider_id 侧别匹配(物业侧 = None,服务商侧 = 非空)

直接调用工厂返回的内部 _check 协程,传入伪造 payload + 哑 user,
不依赖数据库 / FastAPI 依赖注入。
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.core.security import require_provider_roles, require_tenant_roles


class _DummyUser:
    """get_current_user 的返回值占位 —— _check 只是把它原样返回。"""

    def __init__(self, user_id: int = 1) -> None:
        self.id = user_id


def _run(check, payload, user):
    """同步执行 _check 协程并返回结果(或抛出 HTTPException)。"""
    return asyncio.run(check(payload=payload, user=user))


# --- require_tenant_roles -------------------------------------------------


def test_tenant_roles_correct_role_correct_side_returns_user():
    user = _DummyUser(101)
    check = require_tenant_roles("admin", "supervisor")
    payload = {"role": "admin", "provider_id": None}
    assert _run(check, payload, user) is user


def test_tenant_roles_correct_role_wrong_side_403():
    """物业端点 + 服务商侧用户(provider_id 非空)→ 403,即使角色名匹配。"""
    user = _DummyUser(102)
    check = require_tenant_roles("admin")
    payload = {"role": "admin", "provider_id": 7}
    with pytest.raises(HTTPException) as exc:
        _run(check, payload, user)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ERR_FORBIDDEN"
    assert "物业侧" in exc.value.detail["message"]


def test_tenant_roles_wrong_role_403():
    user = _DummyUser(103)
    check = require_tenant_roles("admin", "supervisor")
    payload = {"role": "agent", "provider_id": None}
    with pytest.raises(HTTPException) as exc:
        _run(check, payload, user)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ERR_FORBIDDEN"
    assert "not permitted" in exc.value.detail["message"]


# --- require_provider_roles ----------------------------------------------


def test_provider_roles_correct_role_correct_side_returns_user():
    user = _DummyUser(201)
    check = require_provider_roles("admin", "project_manager")
    payload = {"role": "admin", "provider_id": 42}
    assert _run(check, payload, user) is user


def test_provider_roles_correct_role_wrong_side_403():
    """服务商端点 + 物业侧用户(provider_id 为 None)→ 403,即使角色名匹配。"""
    user = _DummyUser(202)
    check = require_provider_roles("admin")
    payload = {"role": "admin", "provider_id": None}
    with pytest.raises(HTTPException) as exc:
        _run(check, payload, user)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ERR_FORBIDDEN"
    assert "服务商侧" in exc.value.detail["message"]


def test_provider_roles_wrong_role_403():
    user = _DummyUser(203)
    check = require_provider_roles("admin")
    payload = {"role": "project_manager", "provider_id": 42}
    with pytest.raises(HTTPException) as exc:
        _run(check, payload, user)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ERR_FORBIDDEN"
    assert "not permitted" in exc.value.detail["message"]


def test_tenant_roles_missing_provider_id_key_treated_as_property_side():
    """payload 完全没有 provider_id 键 → .get() 返回 None → 视为物业侧放行。"""
    user = _DummyUser(104)
    check = require_tenant_roles("admin")
    payload = {"role": "admin"}
    assert _run(check, payload, user) is user


def test_provider_roles_missing_provider_id_key_403():
    """payload 没有 provider_id 键 → 视为物业侧 → 服务商端点拒绝。"""
    user = _DummyUser(204)
    check = require_provider_roles("admin")
    payload = {"role": "admin"}
    with pytest.raises(HTTPException) as exc:
        _run(check, payload, user)
    assert exc.value.status_code == 403
