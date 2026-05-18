"""短信通道 Task 4 — OTP 端点接线测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.crypto import encrypt_phone
from app.core.security import get_password_hash
from app.models.user import UserAccount
from app.services import sms_center


@pytest.mark.asyncio
async def test_otp_send_calls_sms_in_mock_mode(client, monkeypatch):
    """mock 模式：otp/send 正常返回，dev_code 仍下发，send_otp_sms 被调用。"""
    monkeypatch.setattr(settings, "sms_backend", "mock")
    calls = []
    real = sms_center.send_otp_sms

    def spy(db, *, phone, code, ttl_minutes=5):
        calls.append(phone)
        return real(db, phone=phone, code=code, ttl_minutes=ttl_minutes)

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", spy)
    r = await client.post("/api/v1/auth/otp/send", json={"phone": "13800009999", "purpose": "login"})
    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert len(calls) == 1
    assert r.json()["dev_code"] is not None


@pytest.mark.asyncio
async def test_otp_send_returns_sms_failed_when_send_fails(client, monkeypatch):
    """真实 backend 下 send_otp_sms 失败 → 403 ERR_SMS_SEND_FAILED。"""

    def fail(db, *, phone, code, ttl_minutes=5):
        return sms_center.SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", fail)
    r = await client.post("/api/v1/auth/otp/send", json={"phone": "13800008888", "purpose": "login"})
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_SMS_SEND_FAILED"


# ─── password-reset/request 测试 ──────────────────────────────


@pytest.fixture
def user_for_reset(db_session):
    """手机号为 13866668888 的真实 UserAccount，用于密码重置测试。"""
    user = UserAccount(
        phone_enc=encrypt_phone("13866668888"),
        name="重置测试用户",
        password_hash=get_password_hash("Reset@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.mark.asyncio
async def test_password_reset_user_not_found_no_sms(client, monkeypatch):
    """查不到该手机号用户时，send_otp_sms 不被调用，响应仍 200（防爆破）。"""
    calls = []

    def spy(db, *, phone, code, ttl_minutes=5):
        calls.append(phone)
        return sms_center.SmsResult(ok=True, batch_id="mock")

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", spy)
    r = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"phone": "13700007777"},  # 数据库中不存在
    )
    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert len(calls) == 0


@pytest.mark.asyncio
async def test_password_reset_sms_success(client, monkeypatch, user_for_reset):
    """用户存在 + mock 模式 → 200，send_otp_sms 被调用一次。"""
    monkeypatch.setattr(settings, "sms_backend", "mock")
    calls = []
    real = sms_center.send_otp_sms

    def spy(db, *, phone, code, ttl_minutes=5):
        calls.append(phone)
        return real(db, phone=phone, code=code, ttl_minutes=ttl_minutes)

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", spy)
    r = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"phone": "13866668888"},
    )
    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_password_reset_sms_failure_returns_403(client, monkeypatch, user_for_reset):
    """用户存在 + send_otp_sms 失败 → 403 ERR_SMS_SEND_FAILED。"""

    def fail(db, *, phone, code, ttl_minutes=5):
        return sms_center.SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", fail)
    r = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"phone": "13866668888"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_SMS_SEND_FAILED"
