"""短信通道 Task 3 — sms_center.send_otp_sms 测试。"""
from __future__ import annotations

from app.core.config import settings
from app.core.crypto import encrypt_phone
from app.models.platform import SmsConfig
from app.services import sms_center
from app.services.sms_center import send_otp_sms


def test_mock_backend_returns_ok_without_http(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "mock")
    result = send_otp_sms(db_session, phone="13800001234", code="123456")
    assert result.ok is True
    assert result.batch_id == "mock-otp"


def test_sms_center_no_config_returns_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    result = send_otp_sms(db_session, phone="13800001234", code="123456")
    assert result.ok is False
    assert result.error == "ERR_SMS_NOT_CONFIGURED"


def test_sms_center_template_mode_success(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    db_session.add(SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="有证慧催", otp_template_id="T1001", is_active=True,
    ))
    db_session.flush()
    captured = {}

    def fake_call(body: dict) -> dict:
        captured.update(body)
        return {"code": 0, "msg": None, "data": "batch-999"}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="123456", ttl_minutes=5)
    assert result.ok is True
    assert result.batch_id == "batch-999"
    assert captured["TemplateId"] == "T1001"
    assert captured["TemplateVars"] == ["123456", "5"]
    assert captured["SignName"] == "【有证慧催】"


def test_sms_center_direct_text_mode_when_no_template(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    db_session.add(SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="有证慧催", otp_template_id=None, is_active=True,
    ))
    db_session.flush()
    captured = {}

    def fake_call(body: dict) -> dict:
        captured.update(body)
        return {"code": 0, "msg": None, "data": "b1"}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="654321")
    assert result.ok is True
    assert "654321" in captured["Content"]
    assert captured.get("TemplateId", "") == ""


def test_sms_center_failure_records_last_failure(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    cfg = SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="S", otp_template_id="T1", is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()

    def fake_call(body: dict) -> dict:
        return {"code": 1001, "msg": "余额不足", "data": None}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="111111")
    assert result.ok is False
    assert result.error == "ERR_SMS_SEND_FAILED"
    db_session.refresh(cfg)
    assert cfg.last_failure_at is not None
    assert "余额不足" in cfg.last_failure_reason
