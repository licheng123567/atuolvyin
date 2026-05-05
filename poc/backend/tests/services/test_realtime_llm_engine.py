import asyncio
import time
from datetime import datetime, timezone

import pytest


@pytest.fixture
def fake_case():
    class _Case:
        id = 999
        amount_owed = 2400
        months_overdue = 6
    return _Case()


@pytest.fixture
def fake_owner():
    class _Owner:
        name = "张某某"
        building = "3"
        room = "2-101"
    return _Owner()


def _chunk(seq, text, speaker="customer", utterance_end=True):
    from app.services.streaming_asr import TranscriptChunk
    return TranscriptChunk(
        seq=seq, speaker=speaker, text=text,
        ts=datetime.now(timezone.utc), utterance_end=utterance_end,
    )


@pytest.mark.asyncio
async def test_suggestion_triggered_on_utterance_end_after_debounce(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    calls = []

    async def fake_llm(messages, system_prompt):
        calls.append(messages)
        return {"text": "建议询问分期", "intent": "ask_installment", "confidence": 0.8}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(fake_case, fake_owner, debounce_sec=0)
    s = await engine.on_transcript(_chunk(0, "您好哪位"))
    assert s is not None
    assert s.text == "建议询问分期"
    assert s.id  # uuid generated


@pytest.mark.asyncio
async def test_suggestion_debounce_skips_within_window(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages, system_prompt):
        return {"text": "建议X", "intent": "x", "confidence": 0.9}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(fake_case, fake_owner, debounce_sec=10)
    first = await engine.on_transcript(_chunk(0, "我没钱"))
    assert first is not None
    second = await engine.on_transcript(_chunk(1, "下个月再说"))
    assert second is None  # within debounce window


@pytest.mark.asyncio
async def test_suggestion_timeout_fallback_triggers_when_no_utterance_end(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages, system_prompt):
        return {"text": "建议Y", "intent": "y", "confidence": 0.7}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(
        fake_case, fake_owner, debounce_sec=5, timeout_sec=0
    )
    s = await engine.on_transcript(_chunk(0, "...", utterance_end=False))
    assert s is not None  # timeout=0 forces immediate trigger
    assert s.text == "建议Y"


@pytest.mark.asyncio
async def test_no_suggestion_when_chunk_not_utterance_end_within_timeout(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages, system_prompt):
        pytest.fail("should not call LLM")

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(
        fake_case, fake_owner, debounce_sec=10, timeout_sec=120
    )
    s = await engine.on_transcript(_chunk(0, "...", utterance_end=False))
    assert s is None
