"""v1.7.0 — 业主电话可见性策略：按角色族 × 服务期 / 法务案件状态决定明文 / 脱敏。

设计要点：
1. 决策函数纯函数化（接收 contract_active 等已查好的入参）— 调用方在 endpoint
   入口预先批量查 contract，避免 N+1
2. 包装 display_owner_phone() 内嵌 reveal 决策 → 解密 / 脱敏 → 字符串
3. schema 字段名保持 phone_masked / owner_phone_masked / callee_phone_masked 不变，
   值动态：reveal=True 返回 11 位明文，reveal=False 返回 138****1234 形式

角色族（v1.7.0 决策矩阵）：
- 物业内部 admin/supervisor/agent_internal/property_manager_property → 永远明文
- 服务商 agent_external/property_manager_provider/provider_admin →
    合同 active && expires_at>=now && project.plan_end>=now → 明文，否则脱敏
- 法务 legal → 当前 LegalCase.stage 不在 closed_* → 明文，否则脱敏
- 平台 platform_super/platform_ops → 永远脱敏
- 未识别 → 脱敏（fail-safe）
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone, mask_phone
from app.models.tenant import ProviderTenantContract

INTERNAL_ROLES = frozenset(
    {"admin", "supervisor", "agent_internal", "property_manager_property"}
)
PROVIDER_ROLES = frozenset(
    {"agent_external", "property_manager_provider", "provider_admin"}
)
LEGAL_ROLES = frozenset({"legal"})
PLATFORM_ROLES = frozenset({"platform_super", "platform_superadmin", "platform_ops"})

LEGAL_ACTIVE_STAGES = frozenset(
    {
        "pending_eval",
        "evidence_collection",
        "litigation_filed",
        "judgment_pending",
        "enforcing",
    }
)


def is_provider_contract_active(
    db: Session, tenant_id: int, provider_id: int | None
) -> bool:
    """O(1) 查询 — 服务商 endpoint 入口预取一次，列表渲染复用。

    合同 status='active' 且（expires_at IS NULL 或未过期）即视为有效。
    """
    if provider_id is None:
        return False
    row = db.execute(
        sa.select(ProviderTenantContract.id).where(
            ProviderTenantContract.tenant_id == tenant_id,
            ProviderTenantContract.provider_id == provider_id,
            ProviderTenantContract.status == "active",
            sa.or_(
                ProviderTenantContract.expires_at.is_(None),
                ProviderTenantContract.expires_at >= sa.func.now(),
            ),
        )
    ).scalar_one_or_none()
    return row is not None


def should_reveal_owner_phone(
    *,
    role: str,
    contract_active: bool = False,
    project_active: bool = True,
    legal_case_stage: str | None = None,
) -> bool:
    """根据角色族 + 时效信息决定是否展示明文。

    Args:
        role: token 中的 UserTenantMembership.role 字段
        contract_active: 服务商 ProviderTenantContract 是否有效（仅 PROVIDER_ROLES 用）
        project_active: 当前项目 plan_end 是否未过（仅 PROVIDER_ROLES 用，无项目语境时默认 True）
        legal_case_stage: 当前法务案件 stage（仅 LEGAL_ROLES 用）
    """
    if role in INTERNAL_ROLES:
        return True
    if role in PLATFORM_ROLES:
        return False
    if role in PROVIDER_ROLES:
        return contract_active and project_active
    if role in LEGAL_ROLES:
        return legal_case_stage in LEGAL_ACTIVE_STAGES
    return False


def display_owner_phone(cipher: str | None, *, reveal: bool) -> str | None:
    """根据 reveal 返回明文或脱敏；空输入返回 None。

    用法：调用方先用 should_reveal_owner_phone() 算出 reveal，再传入 cipher。
    """
    if not cipher:
        return None
    return decrypt_phone(cipher) if reveal else mask_phone(cipher)
