from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.risk.keyword_matcher import KeywordHit


@dataclass
class LLMRiskVerdict:
    is_risk: bool
    category: str       # "owner_abuse" | "owner_threat" | "agent_violation" | "agent_minor_misconduct" | "none"
    level: str          # "L1" | "L2" | "none"
    confidence: float
    reason: str


async def analyze_risk_with_llm(
    transcript_text: str,
    speaker: str,
    keyword_hint: KeywordHit | None,
) -> LLMRiskVerdict:
    backend = settings.risk_analyzer_backend.lower()
    if backend == "mock":
        return _mock_analyze(transcript_text, speaker, keyword_hint)
    return await _api_analyze(transcript_text, speaker, keyword_hint)


# ── Mock implementation ───────────────────────────────────────────────────────


def _mock_analyze(
    text: str,
    speaker: str,
    hint: KeywordHit | None,
) -> LLMRiskVerdict:
    """Keyword-only mock: returns verdict based on hint or simple text heuristics."""
    if hint is not None:
        return LLMRiskVerdict(
            is_risk=True,
            category=hint.category,
            level=hint.level,
            confidence=0.90,
            reason=f"keyword match: {hint.keyword}",
        )
    # Simple heuristic for free-form mock
    _AGENT_VIOLATION_HINTS = ["找你家人", "找你单位", "黑名单", "再不还"]
    _BENIGN_HINTS = ["好的", "明白", "知道了", "谢谢"]
    for w in _AGENT_VIOLATION_HINTS:
        if w in text:
            return LLMRiskVerdict(is_risk=True, category="agent_violation", level="L2", confidence=0.88, reason=f"heuristic: {w}")
    for w in _BENIGN_HINTS:
        if w in text:
            return LLMRiskVerdict(is_risk=False, category="none", level="none", confidence=0.95, reason="benign")
    return LLMRiskVerdict(is_risk=False, category="none", level="none", confidence=0.50, reason="no signal")


# ── API implementation ────────────────────────────────────────────────────────


_SYSTEM_PROMPT = """你是专业的催收通话风控判别助手。

根据以下说话者和文本，判断是否属于风险通话片段。严格输出 JSON，字段：
{
  "is_risk": true/false,
  "category": "owner_abuse" | "owner_threat" | "agent_violation" | "agent_minor_misconduct" | "none",
  "level": "L1" | "L2" | "none",
  "confidence": 0.0~1.0,
  "reason": "简短解释（≤50字）"
}

风险类别定义：
- owner_abuse (customer, L1): 业主辱骂催收员（如：你妈、滚、傻逼）
- owner_threat (customer, L2): 业主威胁投诉/法律手段（如：投诉、律师、12345、上法院）
- agent_violation (agent, L2): 催收员违规辱骂或威胁业主（如：再不还、黑名单、找你家人）
- agent_minor_misconduct (agent, L1): 催收员轻微不当言辞（如：随便你、爱交不交）

speaker 字段是输入，不需 LLM 推断。confidence < 0.7 时输出 is_risk=false。"""


async def _api_analyze(
    text: str,
    speaker: str,
    hint: KeywordHit | None,
) -> LLMRiskVerdict:
    import json

    from openai import AsyncOpenAI

    from app.services.llm_openai_compatible import _BASE, _KEY, _MODEL

    client = AsyncOpenAI(api_key=_KEY, base_url=_BASE)
    hint_note = f"\n命中关键词：{hint.keyword}（{hint.category}）" if hint else ""
    user_msg = f"说话者：{speaker}\n文本：{text}{hint_note}"

    resp = await client.chat.completions.create(
        model=_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    try:
        raw = json.loads(resp.choices[0].message.content or "{}")
        confidence = float(raw.get("confidence", 0.0))
        is_risk = bool(raw.get("is_risk", False)) and confidence >= settings.risk_llm_confidence_min
        return LLMRiskVerdict(
            is_risk=is_risk,
            category=raw.get("category", "none") if is_risk else "none",
            level=raw.get("level", "none") if is_risk else "none",
            confidence=confidence,
            reason=raw.get("reason", ""),
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        return LLMRiskVerdict(is_risk=False, category="none", level="none", confidence=0.0, reason="parse_error")
