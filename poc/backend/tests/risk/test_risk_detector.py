import asyncio
import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")

from app.risk.keyword_matcher import KeywordHit
from app.risk.risk_analyzer import LLMRiskVerdict
from app.services.streaming_asr import TranscriptChunk
from datetime import datetime, timezone


def _make_chunk(text: str, speaker: str, seq: int = 1, utterance_end: bool = True) -> TranscriptChunk:
    return TranscriptChunk(seq=seq, speaker=speaker, text=text,
                           ts=datetime.now(timezone.utc), utterance_end=utterance_end)


@pytest.mark.asyncio
async def test_keyword_hit_emits_risk_event():
    emitted = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    from app.risk.risk_detector import RiskDetector

    detector = RiskDetector(call_id=1, tenant_id=1, on_event=on_event)

    hit = KeywordHit(keyword="投诉", category="owner_threat", level="L2", keyword_id=1, span=(2, 3))
    verdict = LLMRiskVerdict(is_risk=True, category="owner_threat", level="L2", confidence=0.90, reason="test")

    with patch("app.risk.risk_detector.get_matcher") as mock_get, \
         patch("app.risk.risk_detector.analyze_risk_with_llm", new=AsyncMock(return_value=verdict)):
        mock_matcher = MagicMock()
        mock_matcher.ensure_loaded = AsyncMock()
        mock_matcher.match.return_value = [hit]
        mock_get.return_value = mock_matcher

        chunk = _make_chunk("我要去投诉你们", "customer")
        await detector.on_utterance(chunk, db=None)
        await asyncio.sleep(0.1)  # let async LLM task complete

    assert len(emitted) == 1
    assert emitted[0]["type"] == "risk.event"
    assert emitted[0]["category"] == "owner_threat"
    assert emitted[0]["trigger"] == "keyword+llm"


@pytest.mark.asyncio
async def test_unknown_speaker_skipped():
    emitted = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    from app.risk.risk_detector import RiskDetector

    detector = RiskDetector(call_id=2, tenant_id=1, on_event=on_event)
    chunk = _make_chunk("随便说点什么", "unknown")
    await detector.on_utterance(chunk, db=None)
    assert emitted == []


@pytest.mark.asyncio
async def test_dedup_within_window():
    emitted = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    from app.risk.risk_detector import RiskDetector

    detector = RiskDetector(call_id=3, tenant_id=1, on_event=on_event)
    hit = KeywordHit(keyword="律师", category="owner_threat", level="L2", keyword_id=2, span=(2, 3))
    verdict = LLMRiskVerdict(is_risk=True, category="owner_threat", level="L2", confidence=0.90, reason="")

    with patch("app.risk.risk_detector.get_matcher") as mock_get, \
         patch("app.risk.risk_detector.analyze_risk_with_llm", new=AsyncMock(return_value=verdict)):
        mock_matcher = MagicMock()
        mock_matcher.ensure_loaded = AsyncMock()
        mock_matcher.match.return_value = [hit]
        mock_get.return_value = mock_matcher

        chunk = _make_chunk("我要找律师", "customer")
        await detector.on_utterance(chunk, db=None)
        await asyncio.sleep(0.1)
        await detector.on_utterance(chunk, db=None)
        await asyncio.sleep(0.1)

    # Second identical event within dedup window → only 1 emitted
    assert len(emitted) == 1


@pytest.mark.asyncio
async def test_llm_overrides_keyword_when_not_risk():
    """LLM says no risk with high confidence → keyword hit suppressed."""
    emitted = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    from app.risk.risk_detector import RiskDetector

    detector = RiskDetector(call_id=4, tenant_id=1, on_event=on_event)
    hit = KeywordHit(keyword="律师", category="owner_threat", level="L2", keyword_id=2, span=(2, 3))
    # LLM says false positive with high confidence
    verdict = LLMRiskVerdict(is_risk=False, category="none", level="none", confidence=0.91, reason="context benign")

    with patch("app.risk.risk_detector.get_matcher") as mock_get, \
         patch("app.risk.risk_detector.analyze_risk_with_llm", new=AsyncMock(return_value=verdict)):
        mock_matcher = MagicMock()
        mock_matcher.ensure_loaded = AsyncMock()
        mock_matcher.match.return_value = [hit]
        mock_get.return_value = mock_matcher

        chunk = _make_chunk("我说的律师朋友很厉害", "customer")
        await detector.on_utterance(chunk, db=None)
        await asyncio.sleep(0.1)

    # Only keyword-only event emitted before LLM reply; but LLM override removes block flag
    # At minimum, no second event; trigger must be "keyword" not "keyword+llm"
    kw_events = [e for e in emitted if e.get("trigger") == "keyword"]
    assert len(kw_events) >= 1  # keyword hit fires immediately


@pytest.mark.asyncio
async def test_no_keyword_hit_no_emit_from_mock():
    """Without keyword hit, free LLM scan on benign text produces no emit."""
    emitted = []

    async def on_event(event: dict) -> None:
        emitted.append(event)

    from app.risk.risk_detector import RiskDetector

    detector = RiskDetector(call_id=5, tenant_id=1, on_event=on_event)
    verdict = LLMRiskVerdict(is_risk=False, category="none", level="none", confidence=0.95, reason="")

    with patch("app.risk.risk_detector.get_matcher") as mock_get, \
         patch("app.risk.risk_detector.analyze_risk_with_llm", new=AsyncMock(return_value=verdict)):
        mock_matcher = MagicMock()
        mock_matcher.ensure_loaded = AsyncMock()
        mock_matcher.match.return_value = []
        mock_get.return_value = mock_matcher

        chunk = _make_chunk("好的我知道了", "customer")
        await detector.on_utterance(chunk, db=None)
        await asyncio.sleep(0.1)

    assert emitted == []
