from app.core import roles


def test_org_roles_are_the_six_functional_roles():
    expected = {"admin", "project_manager", "supervisor", "agent", "legal", "coordinator"}
    assert set(roles.ORG_ROLES) == expected


def test_platform_roles():
    expected = {"superadmin", "ops"}
    assert set(roles.PLATFORM_ROLES) == expected


def test_work_modes():
    expected = {"internal", "external"}
    assert set(roles.WORK_MODES) == expected


def test_legacy_role_map_covers_all_old_values():
    # 每个旧值都映射到一个合法新组织角色
    for old, new in roles.LEGACY_ROLE_MAP.items():
        assert new in roles.ORG_ROLES, f"{old} -> {new} 不是合法组织角色"


def test_role_constants_have_expected_string_values():
    assert roles.ROLE_ADMIN == "admin"
    assert roles.ROLE_PROJECT_MANAGER == "project_manager"
    assert roles.ROLE_SUPERVISOR == "supervisor"
    assert roles.ROLE_AGENT == "agent"
    assert roles.ROLE_LEGAL == "legal"
    assert roles.ROLE_COORDINATOR == "coordinator"
