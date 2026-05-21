"""易保全接入 Task 2/3 — ebaoquan 客户端测试。"""
from __future__ import annotations

import httpx

from app.services import ebaoquan
from app.services.ebaoquan import create_evidence_hash, query_evidence_detail, sign_params


def test_sign_params_doc_vector():
    """证据保全 API 文档 §4.1 给出的签名示例向量。"""
    params = {
        "appKey": "a7ce728fbec40519",
        "param1": "paramValue1",
        "param2": "paramValue2",
        "param3": "paramValue3",
    }
    sign = sign_params(params, "d5207ae9f7bee0692a1e4014f90e1af0")
    assert sign == "2523044EB55944A10324AAAA3DCCEB75"


def test_sign_params_excludes_sign_key():
    """已有 sign 键不参与签名计算。"""
    base = {"appKey": "k", "evidenceId": "96111"}
    with_sign = dict(base, sign="STALE")
    assert sign_params(with_sign, "secret") == sign_params(base, "secret")


def test_sign_params_is_order_independent():
    """参数按 key ASCII 排序，传入顺序不影响结果。"""
    a = sign_params({"b": "2", "a": "1"}, "s")
    b = sign_params({"a": "1", "b": "2"}, "s")
    assert a == b


def test_create_evidence_hash_success(monkeypatch):
    captured = {}

    def fake_post(url: str, params: dict, timeout: float) -> dict:
        captured["url"] = url
        captured["params"] = params
        return {"success": True, "message": None, "code": 0, "data": {"evidenceId": 96111}}

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="案件1通话2录音",
        description="测试物业公司",
        evidence_type="3",
    )
    assert result.ok is True
    assert result.evidence_id == 96111
    assert captured["url"] == "https://bs.sandbox.ebaoquan.org/api/createEvidenceHash"
    assert captured["params"]["sign"]
    assert captured["params"]["type"] == "3"


def test_create_evidence_hash_business_failure(monkeypatch):
    def fake_post(url: str, params: dict, timeout: float) -> dict:
        return {"success": False, "message": "name 不正确", "code": 7201001, "data": None}

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="x",
        description="",
        evidence_type="3",
    )
    assert result.ok is False
    assert result.evidence_id is None
    assert "name 不正确" in result.error


def test_create_evidence_hash_http_exception(monkeypatch):
    def raise_timeout(url: str, params: dict, timeout: float) -> dict:
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ebaoquan, "_post", raise_timeout)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="x",
        description="",
        evidence_type="3",
    )
    assert result.ok is False
    assert result.error == "ERR_EBAOQUAN_HTTP"


def test_query_evidence_detail_success(monkeypatch):
    def fake_post(url: str, params: dict, timeout: float) -> dict:
        assert url.endswith("/api/queryEvidenceDetail")
        return {
            "success": True,
            "message": None,
            "code": 0,
            "data": {"evidenceId": 96, "preservationId": 1852, "type": 1},
        }

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = query_evidence_detail(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        evidence_id=96,
    )
    assert result.ok is True
    assert result.preservation_id == 1852


def test_query_evidence_detail_http_exception(monkeypatch):
    def raise_err(url: str, params: dict, timeout: float) -> dict:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(ebaoquan, "_post", raise_err)
    result = query_evidence_detail(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        evidence_id=96,
    )
    assert result.ok is False
    assert result.error == "ERR_EBAOQUAN_HTTP"
