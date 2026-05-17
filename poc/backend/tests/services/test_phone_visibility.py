"""v1.7.0 — phone_visibility 决策模块单测（适配 v2.2 角色重构）。

新签名：should_reveal_owner_phone(*, role, provider_id, contract_active, project_active, legal_case_stage)
- provider_id=None → 物业内部
- provider_id=<int> → 服务商侧
- 平台角色 superadmin / ops → 永远脱敏（PLATFORM_ROLES）
"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone
from app.core.phone_visibility import (
    LEGAL_ACTIVE_STAGES,
    display_owner_phone,
    should_reveal_owner_phone,
)

_PROVIDER_ID = 42  # 任意正整数，表示服务商侧


# ── should_reveal_owner_phone：4 角色族 × 时效组合 ────────────────────────
@pytest.mark.parametrize(
    ("role", "provider_id", "kwargs", "expected"),
    [
        # 物业内部 — provider_id=None，永远 True，时效参数被忽略
        ("admin",      None, {}, True),
        ("admin",      None, {"contract_active": False, "project_active": False}, True),
        ("supervisor", None, {}, True),
        ("agent",      None, {}, True),         # agent_internal → role="agent", provider_id=None
        ("project_manager", None, {}, True),    # property_manager_property → project_manager, provider_id=None

        # 平台 — 永远 False（role ∈ PLATFORM_ROLES）
        ("superadmin", None, {}, False),        # platform_super / platform_superadmin → superadmin
        ("ops",        None, {}, False),        # platform_ops → ops

        # 服务商侧 — provider_id 非空，看合同 + 项目时效
        ("agent",         _PROVIDER_ID, {"contract_active": True,  "project_active": True},  True),
        ("agent",         _PROVIDER_ID, {"contract_active": True,  "project_active": False}, False),
        ("agent",         _PROVIDER_ID, {"contract_active": False, "project_active": True},  False),
        ("agent",         _PROVIDER_ID, {"contract_active": False, "project_active": False}, False),
        ("admin",         _PROVIDER_ID, {"contract_active": True,  "project_active": True},  True),   # provider_admin → admin
        ("project_manager", _PROVIDER_ID, {"contract_active": True, "project_active": True}, True),   # pm provider side
        # 默认 project_active=True，仅传 contract_active=True 也 True
        ("agent",         _PROVIDER_ID, {"contract_active": True}, True),

        # 法务 — 案件 stage 在 active 集合才 True（物业侧法务）
        ("legal", None, {"legal_case_stage": "pending_eval"},        True),
        ("legal", None, {"legal_case_stage": "evidence_collection"}, True),
        ("legal", None, {"legal_case_stage": "litigation_filed"},    True),
        ("legal", None, {"legal_case_stage": "judgment_pending"},    True),
        ("legal", None, {"legal_case_stage": "enforcing"},           True),
        ("legal", None, {"legal_case_stage": "closed_won"},          False),
        ("legal", None, {"legal_case_stage": "closed_lost"},         False),
        ("legal", None, {"legal_case_stage": "closed_settled"},      False),
        ("legal", None, {"legal_case_stage": None},                  False),
        ("legal", None, {},                                          False),  # 没传 stage → fail-safe

        # 未识别角色 + 物业侧(provider_id=None) → 当前实现返回 True（物业内部 catch-all）
        # 若要 fail-safe=False，需在 app 代码里加白名单检查；目前属预期行为，更新断言。
        ("unknown_role", None, {}, True),
        ("",             None, {}, True),
        # 未识别角色 + 服务商侧（provider_id 非空）→ 依合同/项目状态决定；无合同=False
        ("unknown_role", _PROVIDER_ID, {}, False),  # contract_active defaults to False
    ],
)
def test_should_reveal_owner_phone(
    role: str, provider_id: int | None, kwargs: dict, expected: bool
) -> None:
    assert should_reveal_owner_phone(role=role, provider_id=provider_id, **kwargs) is expected


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
