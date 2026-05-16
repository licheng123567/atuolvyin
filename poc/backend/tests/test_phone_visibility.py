from app.core.phone_visibility import should_reveal_owner_phone


def test_internal_org_role_always_reveal():
    # provider_id=None 即物业内部,永远明文
    assert should_reveal_owner_phone(role="admin", provider_id=None) is True
    assert should_reveal_owner_phone(role="agent", provider_id=None) is True


def test_provider_role_reveal_depends_on_contract():
    # provider_id 非空即服务商侧,看合同 + 项目时效
    assert should_reveal_owner_phone(
        role="agent", provider_id=7, contract_active=True, project_active=True
    ) is True
    assert should_reveal_owner_phone(
        role="agent", provider_id=7, contract_active=False
    ) is False


def test_platform_role_never_reveal():
    assert should_reveal_owner_phone(role="superadmin", provider_id=None) is False
    assert should_reveal_owner_phone(role="ops", provider_id=None) is False


def test_legal_role_depends_on_stage():
    assert should_reveal_owner_phone(
        role="legal", provider_id=None, legal_case_stage="litigation_filed"
    ) is True
    assert should_reveal_owner_phone(
        role="legal", provider_id=None, legal_case_stage="closed_won"
    ) is False
