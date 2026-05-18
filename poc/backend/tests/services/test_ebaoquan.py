"""易保全接入 Task 2/3 — ebaoquan 客户端测试。"""
from __future__ import annotations

from app.services.ebaoquan import sign_params


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
