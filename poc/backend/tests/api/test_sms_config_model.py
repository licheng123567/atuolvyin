"""短信通道 Task 1 — SmsConfig 模型测试。"""
from __future__ import annotations

import sqlalchemy as sa

from app.models.platform import SmsConfig


def test_sms_config_insert_and_query(db_session):
    cfg = SmsConfig(
        secret_name="API",
        secret_key_enc="enc-xxx",
        sign_name="有证慧催",
        otp_template_id="T1001",
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    row = db_session.execute(sa.select(SmsConfig)).scalar_one()
    assert row.secret_name == "API"
    assert row.sign_name == "有证慧催"
    assert row.otp_template_id == "T1001"
    assert row.is_active is True
    assert row.last_failure_at is None


def test_sms_config_optional_fields_nullable(db_session):
    """secret_key_enc / otp_template_id / last_failure_* 可空。"""
    cfg = SmsConfig(secret_name="API2", sign_name="测试签名")
    db_session.add(cfg)
    db_session.flush()
    row = db_session.execute(
        sa.select(SmsConfig).where(SmsConfig.secret_name == "API2")
    ).scalar_one()
    assert row.secret_key_enc is None
    assert row.otp_template_id is None
    assert row.is_active is False
