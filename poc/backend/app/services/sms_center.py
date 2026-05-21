"""短信中心（028lk）OTP 验证码短信客户端。

settings.sms_backend:
  - "mock"        dev / 测试默认：只打 log，不发真实 HTTP。
  - "sms_center"  读 SmsConfig，真实 POST https://api.028lk.com/Sms/Api/Send。

公开入口仅 send_otp_sms()，永不抛异常，统一返回 SmsResult。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_phone
from app.models.platform import SmsConfig

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.028lk.com/Sms/Api/Send"
_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    batch_id: str | None = None
    error: str | None = None


def _mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 11 else "***"


def _call_sms_center(body: dict[str, object]) -> dict[str, object]:
    """真实 HTTP POST 到短信中心，返回解析后的 JSON。失败抛异常。

    测试通过 monkeypatch 替换本函数以模拟 028lk 响应。
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT) as cli:
        resp = cli.post(_ENDPOINT, json=body)
    resp.raise_for_status()
    return resp.json()


def _record_failure(db: Session, config: SmsConfig, reason: str) -> None:
    config.last_failure_at = datetime.now(UTC)
    config.last_failure_reason = reason[:500]
    db.commit()


def send_otp_sms(db: Session, *, phone: str, code: str, ttl_minutes: int = 5) -> SmsResult:
    """发送 OTP 验证码短信。永不抛异常 —— 统一返回 SmsResult。

    失败路径（包括 sms_center 分支的 API 错误）会调用 _record_failure，
    后者执行 db.commit()，会顺带提交当前 Session 中调用方已写入但未提交的行
    （如 OTP 记录）。调用方需知悉此副作用。
    """
    backend = settings.sms_backend.lower()
    if backend == "mock":
        logger.info("[SMS-mock] OTP → %s code=%s ttl=%dmin", _mask_phone(phone), code, ttl_minutes)
        return SmsResult(ok=True, batch_id="mock-otp")

    if backend != "sms_center":
        logger.error("unknown SMS_BACKEND: %s", settings.sms_backend)
        return SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    config = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    if config is None or not config.is_active or not config.secret_key_enc:
        return SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    try:
        secret_key = decrypt_phone(config.secret_key_enc)
    except Exception:
        logger.exception("SmsConfig.secret_key_enc 解密失败")
        return SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    sign = config.sign_name or ""
    if sign and not sign.startswith("【"):
        sign = f"【{sign}】"

    body: dict[str, object] = {
        "SecretName": config.secret_name,
        "SecretKey": secret_key,
        "Mobile": phone,
        "SignName": sign,
    }
    if config.otp_template_id:
        body["TemplateId"] = config.otp_template_id
        body["TemplateVars"] = [code, str(ttl_minutes)]
        body["Content"] = ""
    else:
        body["TemplateId"] = ""
        body["Content"] = f"您的验证码是 {code}，{ttl_minutes} 分钟内有效，请勿泄露。"

    try:
        data = _call_sms_center(body)
    except Exception as exc:  # noqa: BLE001 — 外部 HTTP 任何异常都不应冒泡
        logger.warning("短信中心 HTTP 调用失败: %s", exc)
        _record_failure(db, config, f"HTTP 异常: {exc}")
        return SmsResult(ok=False, error="ERR_SMS_SEND_FAILED")

    if data.get("code") == 0:
        return SmsResult(ok=True, batch_id=str(data.get("data") or ""))

    reason = str(data.get("msg") or f"code={data.get('code')}")
    _record_failure(db, config, reason)
    return SmsResult(ok=False, error="ERR_SMS_SEND_FAILED")
