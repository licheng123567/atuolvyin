"""Realtime LLM suggestion engine — utterance-end + debounce + timeout fallback.

State machine:
  - On each TranscriptChunk:
      trigger if (utterance_end AND debounce_elapsed) OR timeout_hit
  - _last_llm_at is initialised to ``time.monotonic() - debounce_sec`` so
    that the very first utterance-end chunk always fires (debounce already
    elapsed at construction), while the timeout clock starts from construction
    time, preventing a spurious timeout fire on the first chunk when
    timeout_sec is larger than debounce_sec.
  - Do NOT initialise to 0.0 (original plan code): time.monotonic() returns
    thousands of seconds since boot, so ``now - 0`` always exceeds any finite
    timeout_sec, causing the first non-utterance-end chunk to spuriously trigger.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings

from .streaming_asr import TranscriptChunk


@dataclass
class Suggestion:
    id: str
    text: str
    intent: str
    confidence: float

    def to_message(self) -> dict:
        return {
            "type": "suggestion.ready",
            "id": self.id,
            "text": self.text,
            "intent": self.intent,
            "confidence": self.confidence,
        }


@dataclass
class _CaseCtx:
    case: object
    owner: object
    transcript: list[TranscriptChunk] = field(default_factory=list)


class RealtimeSuggestionEngine:
    def __init__(
        self,
        case: object,
        owner: object,
        debounce_sec: Optional[int] = None,
        timeout_sec: Optional[int] = None,
    ):
        self._ctx = _CaseCtx(case=case, owner=owner)
        self._debounce_sec = (
            debounce_sec if debounce_sec is not None else settings.realtime_llm_debounce_sec
        )
        self._timeout_sec = (
            timeout_sec if timeout_sec is not None else settings.realtime_llm_timeout_sec
        )
        # Initialise to (now - debounce_sec) so the first utterance-end chunk
        # always triggers (debounce already elapsed), while remaining recent
        # enough that a finite timeout_sec > debounce_sec does NOT fire on the
        # very first chunk.
        self._last_llm_at: float = time.monotonic() - self._debounce_sec

    async def on_transcript(self, chunk: TranscriptChunk) -> Optional[Suggestion]:
        self._ctx.transcript.append(chunk)
        now = time.monotonic()

        elapsed = now - self._last_llm_at
        debounce_elapsed = elapsed >= self._debounce_sec
        timeout_hit = elapsed >= self._timeout_sec

        should_trigger = (chunk.utterance_end and debounce_elapsed) or timeout_hit
        if not should_trigger:
            return None

        self._last_llm_at = now
        return await self._invoke_llm()

    async def on_call_ended(self) -> dict:
        """Final call analysis returned as a payload dict for tag.ready."""
        result = await _call_final_analysis(self._build_messages(final=True))
        return result

    async def _invoke_llm(self) -> Suggestion:
        result = await _call_llm(self._build_messages(final=False))
        return Suggestion(
            id=str(uuid.uuid4()),
            text=result.get("text", ""),
            intent=result.get("intent", "unknown"),
            confidence=float(result.get("confidence", 0.0)),
        )

    def _build_messages(self, final: bool) -> list[dict]:
        owner_name = getattr(self._ctx.owner, "name", "未知")
        amount = getattr(self._ctx.case, "amount_owed", 0)
        months = getattr(self._ctx.case, "months_overdue", 0)
        history = "\n".join(
            f"[{c.speaker}] {c.text}" for c in self._ctx.transcript[-10:]
        )
        if final:
            prompt = (
                f"以下是与业主 {owner_name}（欠费 {amount} / {months} 月）"
                f"的完整通话记录，请输出最终分析（intent / promise_date / promise_amount / summary）：\n\n{history}"
            )
        else:
            prompt = (
                f"以下是与业主 {owner_name}（欠费 {amount} / {months} 月）"
                f"的对话片段，请基于业主最近一句生成 1 条话术建议：\n\n{history}"
            )
        return [{"role": "user", "content": prompt}]


async def _call_llm(messages: list[dict]) -> dict:
    """Default impl calls the LLM backend directly with an OpenAI-compatible
    messages list.  Tests monkeypatch this module-level symbol so they never
    reach this path.

    The existing app.services.llm only exposes extract(task_type, task_payload,
    transcript) — a post-call batch API.  Realtime suggestions need a
    messages-based chat completion, so we call the backend directly here
    rather than routing through llm.extract().
    """
    backend = settings.llm_backend.lower()
    if backend == "mock":
        # Return a sensible mock suggestion
        return {
            "text": "建议确认业主方便的还款时间",
            "intent": "ask_payment_schedule",
            "confidence": 0.75,
        }
    if backend == "api":
        import json
        from openai import AsyncOpenAI

        _BASE = settings.llm_base_url or "https://api.deepseek.com"
        _KEY = settings.llm_api_key or "sk-placeholder"
        _MODEL = settings.llm_model or "deepseek-chat"

        system = (
            "你是物业费催收实时辅助助手。根据业主最近一句话，给坐席生成 1 条简短话术建议。"
            "严格输出 JSON，字段：{\"text\": \"建议内容\", \"intent\": \"意图标签\", \"confidence\": 0~1}"
            "不要输出 JSON 以外的任何内容。"
        )
        full_messages = [{"role": "system", "content": system}] + messages

        client = AsyncOpenAI(api_key=_KEY, base_url=_BASE)
        resp = await client.chat.completions.create(
            model=_MODEL,
            messages=full_messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    raise RuntimeError(f"unknown LLM_BACKEND: {settings.llm_backend}")


async def _call_final_analysis(messages: list[dict]) -> dict:
    """Final call analysis — delegates to the existing extract() API which
    already handles both mock and api backends for post-call collection tasks."""
    # Build a plain transcript string from the messages prompt
    prompt_content = messages[-1]["content"] if messages else ""

    backend = settings.llm_backend.lower()
    if backend == "mock":
        return {
            "intent": "承诺缴",
            "promise_date": None,
            "promise_amount": None,
            "summary": prompt_content[:100],
            "needs_review": True,
        }
    if backend == "api":
        import json
        from openai import AsyncOpenAI

        _BASE = settings.llm_base_url or "https://api.deepseek.com"
        _KEY = settings.llm_api_key or "sk-placeholder"
        _MODEL = settings.llm_model or "deepseek-chat"

        system = (
            "你是物业费催收通话分析助手。根据完整通话记录，输出最终分析。"
            "严格输出 JSON，字段：{\"intent\": \"...\", \"promise_date\": \"YYYY-MM-DD或null\","
            "\"promise_amount\": number或null, \"summary\": \"...\", \"needs_review\": true/false}"
            "不要输出 JSON 以外的任何内容。"
        )
        client = AsyncOpenAI(api_key=_KEY, base_url=_BASE)
        resp = await client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": system}] + messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content or "{}"
        result = json.loads(content)
        return {
            "intent": result.get("intent", "unknown"),
            "promise_date": result.get("promise_date"),
            "promise_amount": result.get("promise_amount"),
            "summary": result.get("summary", ""),
            "needs_review": bool(result.get("needs_review", True)),
        }

    raise RuntimeError(f"unknown LLM_BACKEND: {settings.llm_backend}")
