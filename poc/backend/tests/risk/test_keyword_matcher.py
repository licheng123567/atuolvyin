import time
import pytest
from unittest.mock import patch

from app.risk.keyword_matcher import RiskKeywordMatcher, KeywordHit, get_matcher, _matchers


@pytest.fixture(autouse=True)
def clear_matcher_cache():
    _matchers.clear()
    yield
    _matchers.clear()


@pytest.fixture
def mock_db_keywords():
    """Returns a list of (keyword, category, level, id) tuples for tenant 1, speaker 'customer'."""
    return [
        ("投诉", "owner_threat", "L2", 1),
        ("律师", "owner_threat", "L2", 2),
        ("你妈", "owner_abuse",  "L1", 3),
    ]


async def _make_loaded_matcher(mock_db_keywords, tenant_id=1, speaker="customer"):
    matcher = RiskKeywordMatcher(tenant_id=tenant_id, speaker=speaker)

    def sync_load(db):
        import ahocorasick
        A = ahocorasick.Automaton()
        for kw, cat, lv, kid in mock_db_keywords:
            A.add_word(kw, (kw, cat, lv, kid))
        A.make_automaton()
        matcher._automaton = A
        matcher._loaded_at = time.monotonic()

    with patch.object(matcher, "_load_from_db", side_effect=sync_load):
        await matcher.ensure_loaded(db=None)
    return matcher


@pytest.mark.asyncio
async def test_single_keyword_hit(mock_db_keywords):
    matcher = await _make_loaded_matcher(mock_db_keywords)
    hits = matcher.match("我去投诉你们公司")
    assert len(hits) == 1
    assert hits[0].keyword == "投诉"
    assert hits[0].category == "owner_threat"
    assert hits[0].level == "L2"


@pytest.mark.asyncio
async def test_multiple_keywords_in_one_utterance(mock_db_keywords):
    matcher = await _make_loaded_matcher(mock_db_keywords)
    hits = matcher.match("你妈的我要找律师")
    assert {h.keyword for h in hits} == {"你妈", "律师"}


@pytest.mark.asyncio
async def test_no_hit_returns_empty(mock_db_keywords):
    matcher = await _make_loaded_matcher(mock_db_keywords)
    hits = matcher.match("我明天把钱转给你")
    assert hits == []


@pytest.mark.asyncio
async def test_ttl_expiry_triggers_reload(mock_db_keywords):
    matcher = await _make_loaded_matcher(mock_db_keywords)
    matcher._loaded_at = time.monotonic() - 61
    reload_called = False

    def fake_reload(db):
        nonlocal reload_called
        reload_called = True
        matcher._loaded_at = time.monotonic()

    with patch.object(matcher, "_load_from_db", side_effect=fake_reload):
        await matcher.ensure_loaded(db=None)
    assert reload_called


@pytest.mark.asyncio
async def test_get_matcher_returns_same_instance():
    m1 = get_matcher(tenant_id=1, speaker="agent")
    m2 = get_matcher(tenant_id=1, speaker="agent")
    assert m1 is m2
    m3 = get_matcher(tenant_id=1, speaker="customer")
    assert m1 is not m3


@pytest.mark.asyncio
async def test_empty_keyword_list_returns_no_hits():
    matcher = RiskKeywordMatcher(tenant_id=1, speaker="customer")

    def empty_load(db):
        import ahocorasick
        matcher._automaton = ahocorasick.Automaton()  # empty — make_automaton NOT called
        matcher._loaded_at = time.monotonic()

    with patch.object(matcher, "_load_from_db", side_effect=empty_load):
        await matcher.ensure_loaded(db=None)

    assert matcher.match("任何文本") == []
