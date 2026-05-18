"""易保全证据保全（ebaoquan.org）API 客户端。

纯 HTTP seam，不碰 DB，永不抛异常。公开函数：
  - sign_params()           证据保全 API 文档 §4.1 签名算法
  - create_evidence_hash()  HASH 保全 → EbaoquanHashResult
  - query_evidence_detail() 证据详情（取保全备案号）→ EbaoquanDetailResult
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class EbaoquanHashResult:
    ok: bool
    evidence_id: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class EbaoquanDetailResult:
    ok: bool
    preservation_id: int | None = None
    error: str | None = None


def sign_params(params: dict[str, str], app_key_secret: str) -> str:
    """易保全签名 §4.1：参数（排除 sign）按 key ASCII 升序拼 k=v&k=v，
    尾接 appKeySecret，MD5 后全大写。"""
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    string_a = "&".join(f"{k}={v}" for k, v in items)
    string_sign_temp = string_a + app_key_secret
    return hashlib.md5(string_sign_temp.encode("utf-8")).hexdigest().upper()
