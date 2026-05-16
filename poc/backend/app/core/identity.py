"""登录身份解析(v2.2 角色重构)。

合并原先散在 auth.py / auth_extras.py 的三处重复逻辑。
平台身份(UserAccount.platform_role)优先;否则取组织 membership。
无平台身份且无 membership → 拒绝(不再默认超管)。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount


@dataclass(frozen=True)
class IdentityClaims:
    role: str
    scope: str  # 'platform' | 'tenant:{id}' | 'provider:{id}'
    tenant_id: int | None
    provider_id: int | None
    tenant_name: str | None


def resolve_identity(
    db: Session,
    user: UserAccount,
    membership: UserTenantMembership | None = None,
) -> IdentityClaims:
    """算出登录后写进 JWT 的身份声明。

    membership 显式传入时(如 select-membership 切换角色)直接用它;
    否则取该用户第一条有效 membership。
    """
    # 不变量:平台用户(platform_role 非空)没有任何组织 membership
    # (迁移删除了平台 membership 行,seed 也不给平台用户建 membership)。
    # 因此显式传入的 membership 参数只对非平台用户生效。
    # 1. 平台身份优先
    if user.platform_role:
        return IdentityClaims(
            role=user.platform_role,
            scope="platform",
            tenant_id=None,
            provider_id=None,
            tenant_name=None,
        )

    # 2. 组织 membership
    if membership is None:
        membership = db.execute(
            select(UserTenantMembership)
            .where(
                UserTenantMembership.user_id == user.id,
                UserTenantMembership.is_active.is_(True),
            )
            .limit(1)
        ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_ROLE", "message": "账号未分配任何角色,请联系管理员"},
        )

    scope = (
        f"provider:{membership.provider_id}"
        if membership.provider_id is not None
        else f"tenant:{membership.tenant_id}"
    )
    tenant_name = db.execute(
        select(Tenant.name).where(Tenant.id == membership.tenant_id)
    ).scalar_one_or_none()

    return IdentityClaims(
        role=membership.role,
        scope=scope,
        tenant_id=membership.tenant_id,
        provider_id=membership.provider_id,
        tenant_name=tenant_name,
    )
