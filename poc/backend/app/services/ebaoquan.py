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


def _post(url: str, params: dict[str, str], timeout: float) -> dict[str, Any]:
    """真实 HTTP POST（form-urlencoded），返回解析后的 JSON。失败抛异常。

    测试通过 monkeypatch 替换本函数以模拟易保全响应。
    """
    with httpx.Client(timeout=timeout) as cli:
        resp = cli.post(url, data=params)
    resp.raise_for_status()
    return resp.json()


def create_evidence_hash(
    *,
    base_url: str,
    app_key: str,
    app_key_secret: str,
    file_hash: str,
    name: str,
    description: str,
    evidence_type: str,
    timeout: float = _HTTP_TIMEOUT,
) -> EbaoquanHashResult:
    """HASH 保全：POST /api/createEvidenceHash。永不抛异常。"""
    params: dict[str, str] = {
        "appKey": app_key,
        "fileHash": file_hash,
        "name": name,
        "description": description,
        "type": evidence_type,
    }
    params["sign"] = sign_params(params, app_key_secret)
    url = base_url.rstrip("/") + "/api/createEvidenceHash"
    try:
        data = _post(url, params, timeout)
    except Exception as exc:  # noqa: BLE001 — 外部 HTTP 任何异常都不应冒泡
        logger.warning("易保全 createEvidenceHash HTTP 调用失败: %s", exc)
        return EbaoquanHashResult(ok=False, error="ERR_EBAOQUAN_HTTP")

    if data.get("code") == 0:
        payload = data.get("data") or {}
        evidence_id = payload.get("evidenceId")
        if evidence_id is None:
            return EbaoquanHashResult(ok=False, error="ERR_EBAOQUAN_NO_EVIDENCE_ID")
        return EbaoquanHashResult(ok=True, evidence_id=int(evidence_id))

    reason = str(data.get("message") or f"code={data.get('code')}")
    return EbaoquanHashResult(ok=False, error=reason)


def query_evidence_detail(
    *,
    base_url: str,
    app_key: str,
    app_key_secret: str,
    evidence_id: int,
    timeout: float = _HTTP_TIMEOUT,
) -> EbaoquanDetailResult:
    """证据详情：POST /api/queryEvidenceDetail，取保全备案号。永不抛异常。"""
    params: dict[str, str] = {
        "appKey": app_key,
        "evidenceId": str(evidence_id),
    }
    params["sign"] = sign_params(params, app_key_secret)
    url = base_url.rstrip("/") + "/api/queryEvidenceDetail"
    try:
        data = _post(url, params, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("易保全 queryEvidenceDetail HTTP 调用失败: %s", exc)
        return EbaoquanDetailResult(ok=False, error="ERR_EBAOQUAN_HTTP")

    if data.get("code") == 0:
        payload = data.get("data") or {}
        pid = payload.get("preservationId")
        return EbaoquanDetailResult(
            ok=True, preservation_id=int(pid) if pid is not None else None
        )

    reason = str(data.get("message") or f"code={data.get('code')}")
    return EbaoquanDetailResult(ok=False, error=reason)
