"""v1.7.0 — phone_visibility 决策模块单测。"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone
from app.core.phone_visibility import (
    LEGAL_ACTIVE_STAGES,
    display_owner_phone,
    should_reveal_owner_phone,
)


# ── should_reveal_owner_phone：4 角色族 × 时效组合 ────────────────────────
@pytest.mark.parametrize(
    ("role", "kwargs", "expected"),
    [
        # 物业内部 — 永远 True，时效参数被忽略
        ("admin", {}, True),
        ("admin", {"contract_active": False, "project_active": False}, True),
        ("supervisor", {}, True),
        ("agent_internal", {}, True),
        ("property_manager_property", {}, True),

        # 平台 — 永远 False
        ("platform_super", {}, False),
        ("platform_superadmin", {}, False),
        ("platform_ops", {}, False),

        # 服务商 — 合同 + 项目都活才 True
        ("agent_external", {"contract_active": True, "project_active": True}, True),
        ("agent_external", {"contract_active": True, "project_active": False}, False),
        ("agent_external", {"contract_active": False, "project_active": True}, False),
        ("agent_external", {"contract_active": False, "project_active": False}, False),
        ("provider_admin", {"contract_active": True, "project_active": True}, True),
        ("property_manager_provider", {"contract_active": True, "project_active": True}, True),
        # 默认 project_active=True，仅传 contract_active=True 也 True
        ("agent_external", {"contract_active": True}, True),

        # 法务 — 案件 stage 在 active 集合才 True
        ("legal", {"legal_case_stage": "pending_eval"}, True),
        ("legal", {"legal_case_stage": "evidence_collection"}, True),
        ("legal", {"legal_case_stage": "litigation_filed"}, True),
        ("legal", {"legal_case_stage": "judgment_pending"}, True),
        ("legal", {"legal_case_stage": "enforcing"}, True),
        ("legal", {"legal_case_stage": "closed_won"}, False),
        ("legal", {"legal_case_stage": "closed_lost"}, False),
        ("legal", {"legal_case_stage": "closed_settled"}, False),
        ("legal", {"legal_case_stage": None}, False),
        ("legal", {}, False),  # 没传 stage → fail-safe

        # 未识别角色 — fail-safe False
        ("unknown_role", {}, False),
        ("", {}, False),
    ],
)
def test_should_reveal_owner_phone(role: str, kwargs: dict, expected: bool) -> None:
    assert should_reveal_owner_phone(role=role, **kwargs) is expected


def test_legal_active_stages_excludes_closed() -> None:
    """sanity check：active 集合不能包含 closed_*"""
    closed_stages = {"closed_won", "closed_lost", "closed_settled"}
    assert closed_stages.isdisjoint(LEGAL_ACTIVE_STAGES)


# ── display_owner_phone：解密 / 脱敏 / 空值分支 ─────────────────────────
def test_display_owner_phone_reveal_returns_plain() -> None:
    cipher = encrypt_phone("13800001234")
    assert display_owner_phone(cipher, reveal=True) == "13800001234"


def test_display_owner_phone_no_reveal_returns_masked() -> None:
    cipher = encrypt_phone("13800001234")
    assert display_owner_phone(cipher, reveal=False) == "138****1234"


@pytest.mark.parametrize("cipher", [None, ""])
def test_display_owner_phone_empty_returns_none(cipher: str | None) -> None:
    assert display_owner_phone(cipher, reveal=True) is None
    assert display_owner_phone(cipher, reveal=False) is None
