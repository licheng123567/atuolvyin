"""v1.5.5 — 邮件发送 dispatcher（参照 services/asr.py 范式）。

后端：
    - console (默认)：dev 模式 stdout 打印，零依赖
    - smtp：SMTP 投递（v1.5.6 接入）
    - ses：AWS SES（v1.5.6 接入）
"""
from __future__ import annotations

from app.core.config import settings


def send_email(to: str, subject: str, body: str) -> dict:
    backend = settings.email_backend.lower()
    if backend == "console":
        print(f"[EMAIL/console] to={to}\n  subject: {subject}\n  body:\n{body}\n")
        return {"sent": True, "backend": "console"}
    if backend == "smtp":
        raise NotImplementedError("smtp backend pending v1.5.6")
    if backend == "ses":
        raise NotImplementedError("ses backend pending v1.5.6")
    raise RuntimeError(f"unknown EMAIL_BACKEND: {settings.email_backend}")
