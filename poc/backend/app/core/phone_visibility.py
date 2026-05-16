"""v2.2 — 业主电话可见性策略：按组织归属(provider_id) × 角色 × 服务期 / 法务案件状态决定明文 / 脱敏。

设计要点：
1. 决策函数纯函数化（接收 contract_active / provider_id 等已查好的入参）— 调用方在 endpoint
   入口预先批量查 contract，避免 N+1
2. 包装 display_owner_phone() 内嵌 reveal 决策 → 解密 / 脱敏 → 字符串
3. schema 字段名保持 phone_masked / owner_phone_masked / callee_phone_masked 不变，
   值动态：reveal=True 返回 11 位明文，reveal=False 返回 138****1234 形式

决策矩阵（v2.2）：
- 平台角色 superadmin/ops → 永远脱敏
- legal → 当前 LegalCase.stage 在 LEGAL_ACTIVE_STAGES → 明文，否则脱敏
- provider_id 非空（服务商侧）→ 合同 active && 项目 plan_end 未过 → 明文，否则脱敏
- provider_id=None（物业内部） → 永远明文
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone, mask_phone
from app.core.roles import PLATFORM_ROLES, ROLE_LEGAL
from app.models.tenant import ProviderTenantContract

LEGAL_ACTIVE_STAGES = frozenset(
    {
        "pending_eval",
        "evidence_collection",
        "litigation_filed",
        "judgment_pending",
        "enforcing",
    }
)


def is_provider_contract_active(db: Session, tenant_id: int, provider_id: int | None) -> bool:
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
    provider_id: int | None,
    contract_active: bool = False,
    project_active: bool = True,
    legal_case_stage: str | None = None,
) -> bool:
    """根据组织归属 + 角色 + 时效信息决定是否展示明文业主电话。

    Args:
        role: token 中的角色(组织职能角色或平台角色)
        provider_id: 组织归属 —— None=物业内部,非空=服务商
        contract_active: 服务商 ProviderTenantContract 是否有效(仅服务商侧用)
        project_active: 当前项目 plan_end 是否未过(仅服务商侧用,无项目语境默认 True)
        legal_case_stage: 当前法务案件 stage(仅 legal 角色用)
    """
    # 平台角色 —— 永远脱敏
    if role in PLATFORM_ROLES:
        return False
    # 法务 —— 看案件阶段(物业法务 / 服务商法务同规则)
    if role == ROLE_LEGAL:
        return legal_case_stage in LEGAL_ACTIVE_STAGES
    # 服务商侧 —— 看合同 + 项目时效
    if provider_id is not None:
        return contract_active and project_active
    # 物业内部 —— 永远明文
    return True


def display_owner_phone(cipher: str | None, *, reveal: bool) -> str | None:
    """根据 reveal 返回明文或脱敏；空输入返回 None。

    用法：调用方先用 should_reveal_owner_phone() 算出 reveal，再传入 cipher。
    """
    if not cipher:
        return None
    return decrypt_phone(cipher) if reveal else mask_phone(cipher)
