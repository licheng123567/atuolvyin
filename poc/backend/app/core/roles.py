"""角色模型单一事实源(v2.2 角色重构)。

禁止在其他文件再散落角色字符串字面量 —— 一律从这里 import。

四个维度:
- 平台身份  UserAccount.platform_role  ∈ PLATFORM_ROLES | None
- 组织职能  UserTenantMembership.role  ∈ ORG_ROLES
- 组织归属  UserTenantMembership.provider_id  None=物业侧 / int=服务商侧
- 工作方式  UserTenantMembership.work_mode  ∈ WORK_MODES | None(仅 agent)
"""

from __future__ import annotations

# ─── 组织职能角色 ──────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_PROJECT_MANAGER = "project_manager"
ROLE_SUPERVISOR = "supervisor"
ROLE_AGENT = "agent"
ROLE_LEGAL = "legal"
ROLE_COORDINATOR = "coordinator"

ORG_ROLES = frozenset(
    {ROLE_ADMIN, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, ROLE_AGENT, ROLE_LEGAL, ROLE_COORDINATOR}
)

# ─── 平台身份 ─────────────────────────────────────────────────
PLATFORM_SUPERADMIN = "superadmin"
PLATFORM_OPS = "ops"
PLATFORM_ROLES = frozenset({PLATFORM_SUPERADMIN, PLATFORM_OPS})

# ─── 工作方式(仅 agent)──────────────────────────────────────
WORK_INTERNAL = "internal"
WORK_EXTERNAL = "external"
WORK_MODES = frozenset({WORK_INTERNAL, WORK_EXTERNAL})

# ─── 旧值 → 新值映射(迁移 + seed + 测试共用)────────────────
LEGACY_ROLE_MAP: dict[str, str] = {
    "admin": ROLE_ADMIN,
    "provider_admin": ROLE_ADMIN,
    "supervisor": ROLE_SUPERVISOR,
    "agent_internal": ROLE_AGENT,
    "agent_external": ROLE_AGENT,
    "legal": ROLE_LEGAL,
    "coordinator": ROLE_COORDINATOR,
    "project_manager_property": ROLE_PROJECT_MANAGER,
    "project_manager_provider": ROLE_PROJECT_MANAGER,
    "property_manager_property": ROLE_PROJECT_MANAGER,
    "property_manager_provider": ROLE_PROJECT_MANAGER,
}

# 旧 agent 角色 → work_mode
LEGACY_WORK_MODE_MAP: dict[str, str] = {
    "agent_internal": WORK_INTERNAL,
    "agent_external": WORK_EXTERNAL,
}

# 旧平台 membership.role → platform_role
LEGACY_PLATFORM_ROLE_MAP: dict[str, str] = {
    "platform_ops": PLATFORM_OPS,
    "platform_superadmin": PLATFORM_SUPERADMIN,
    "platform_super": PLATFORM_SUPERADMIN,
}
