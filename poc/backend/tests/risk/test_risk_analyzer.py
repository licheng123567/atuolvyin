import os
import pytest

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")


@pytest.mark.asyncio
async def test_mock_keyword_hint_returns_verdict():
    from app.risk.risk_analyzer import analyze_risk_with_llm
    from app.risk.keyword_matcher import KeywordHit

    hint = KeywordHit(keyword="投诉", category="owner_threat", level="L2", keyword_id=1, span=(2, 3))
    verdict = await analyze_risk_with_llm(
        transcript_text="我要去投诉你们",
        speaker="customer",
        keyword_hint=hint,
    )
    assert verdict.is_risk is True
    assert verdict.category == "owner_threat"
    assert verdict.confidence >= 0.7


@pytest.mark.asyncio
async def test_low_confidence_verdict_is_not_risk():
    from app.risk.risk_analyzer import analyze_risk_with_llm

    # Mock backend returns is_risk=False for benign text
    verdict = await analyze_risk_with_llm(
        transcript_text="好的我知道了",
        speaker="customer",
        keyword_hint=None,
    )
    assert verdict.is_risk is False


@pytest.mark.asyncio
async def test_mock_no_hint_still_returns_verdict():
    from app.risk.risk_analyzer import analyze_risk_with_llm

    verdict = await analyze_risk_with_llm(
        transcript_text="再不还钱找你家人",
        speaker="agent",
        keyword_hint=None,
    )
    # Mock returns is_risk=True for text containing 找你家人
    assert verdict.is_risk is True
    assert verdict.category == "agent_violation"
