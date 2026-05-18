"""短信通道 Task 4 — OTP 端点接线测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings
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


@pytest.mark.asyncio
async def test_otp_send_returns_sms_failed_when_send_fails(client, monkeypatch):
    """真实 backend 下 send_otp_sms 失败 → 403 ERR_SMS_SEND_FAILED。"""
    monkeypatch.setattr(settings, "sms_backend", "sms_center")

    def fail(db, *, phone, code, ttl_minutes=5):
        return sms_center.SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", fail)
    r = await client.post("/api/v1/auth/otp/send", json={"phone": "13800008888", "purpose": "login"})
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_SMS_SEND_FAILED"
