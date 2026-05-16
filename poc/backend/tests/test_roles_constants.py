from app.core import roles


def test_org_roles_are_the_six_functional_roles():
    assert roles.ORG_ROLES == frozenset(
        {"admin", "project_manager", "supervisor", "agent", "legal", "coordinator"}
    )


def test_platform_roles():
    assert roles.PLATFORM_ROLES == frozenset({"superadmin", "ops"})


def test_work_modes():
    assert roles.WORK_MODES == frozenset({"internal", "external"})


def test_legacy_role_map_covers_all_old_values():
    # 每个旧值都映射到一个合法新组织角色
    for old, new in roles.LEGACY_ROLE_MAP.items():
        assert new in roles.ORG_ROLES, f"{old} -> {new} 不是合法组织角色"


def test_constants_are_uppercase_module_level():
    assert isinstance(roles.ROLE_ADMIN, str) and roles.ROLE_ADMIN == "admin"
