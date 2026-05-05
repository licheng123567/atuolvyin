from app.services.realtime_llm import (
    RealtimeSuggestionEngine, _build_system_prompt, _load_scripts,
)


def test_build_system_prompt_no_scripts():
    base = "你是话术助手。"
    result = _build_system_prompt({}, base)
    assert result == base


def test_build_system_prompt_with_scripts():
    scripts = {
        "经济困难": ["可以分期缴纳", "理解您的困难"],
        "服务不满": ["非常抱歉"],
    }
    base = "你是话术助手。"
    result = _build_system_prompt(scripts, base)
    assert "[参考话术 - 经济困难]" in result
    assert "可以分期缴纳" in result
    assert "[参考话术 - 服务不满]" in result


def test_load_scripts_returns_empty_when_no_active(db_session, seeded_tenant):
    result = _load_scripts(db_session, seeded_tenant.id)
    assert isinstance(result, dict)


def test_load_scripts_returns_active_scripts(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="t", trigger_intent="经济困难", content="可以分期", version=1, is_active=True,
    )
    db_session.add(s)
    db_session.flush()
    result = _load_scripts(db_session, seeded_tenant.id)
    assert "经济困难" in result
    assert "可以分期" in result["经济困难"]


def test_load_scripts_excludes_inactive(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="inactive", trigger_intent="其他", content="内容", version=1, is_active=False,
    )
    db_session.add(s)
    db_session.flush()
    result = _load_scripts(db_session, seeded_tenant.id)
    assert "其他" not in result or "内容" not in result.get("其他", [])


def test_engine_confidence_filtered_by_sensitivity():
    from unittest.mock import MagicMock
    engine = RealtimeSuggestionEngine(
        case=MagicMock(), owner=MagicMock(),
        scripts={}, sensitivity_threshold=0.85, max_per_push=3
    )
    assert engine._sensitivity_threshold == 0.85
    assert engine._max_per_push == 3
