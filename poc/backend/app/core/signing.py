"""HMAC 签名 URL：用于本地文件存储模式下给 ASR 提供短期可访问链接。

验证逻辑里把 secret 与 path + 过期时间一起 HMAC，外部无法伪造。
"""

import base64
import hashlib
import hmac
import time

from .config import settings


def _secret() -> bytes:
    return settings.recording_sign_secret.encode("utf-8")


def make_token(object_key: str, expires_sec: int) -> tuple[str, int]:
    """返回 (token, exp_unix)。"""
    exp = int(time.time()) + expires_sec
    msg = f"{object_key}|{exp}".encode()
    sig = hmac.new(_secret(), msg, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return token, exp


def verify_token(object_key: str, token: str, exp: int) -> bool:
    if exp < int(time.time()):
        return False
    expected, _ = make_token_with_exp(object_key, exp)
    return hmac.compare_digest(expected, token)


def make_token_with_exp(object_key: str, exp: int) -> tuple[str, int]:
    msg = f"{object_key}|{exp}".encode()
    sig = hmac.new(_secret(), msg, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return token, exp
