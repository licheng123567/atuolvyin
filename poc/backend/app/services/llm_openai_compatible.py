"""OpenAI 兼容协议 LLM 抽取：DeepSeek / Ollama / Qwen DashScope-OpenAI 兼容端点都用此实现。

按 settings.llm_base_url + llm_model + llm_api_key 选择。
"""

import json

from openai import OpenAI

from app.core.config import settings

# 兼容旧 .env 的 deepseek_* 字段
_BASE = settings.llm_base_url or settings.deepseek_base_url or "https://api.deepseek.com"
_KEY = settings.llm_api_key or settings.deepseek_api_key or "sk-placeholder"
_MODEL = settings.llm_model or settings.deepseek_model or "deepseek-chat"

_client = OpenAI(api_key=_KEY, base_url=_BASE)


VOTE_SYSTEM = """你是物业投票通话分析助手。请仅根据下面给出的通话文字稿，抽取业主的投票表态。
严格输出 JSON，字段：
{
  "choice": "同意" | "反对" | "弃权" | "未明确",
  "reason": "业主表态的关键理由（≤100 字）",
  "compliance_disclosed": true/false,
  "confidence": 0~1 的小数,
  "needs_review": true/false
}
不要输出 JSON 以外的任何内容。"""

COLLECTION_SYSTEM = """你是物业费催收通话分析助手。请仅根据下面给出的通话文字稿，抽取催收结果。
严格输出 JSON，字段：
{
  "intent": "立即缴" | "承诺缴" | "推托" | "拒缴" | "失联",
  "promise_date": "YYYY-MM-DD 或 null",
  "excuse_category": "房屋质量" | "服务不满" | "经济困难" | "失业" | "其他" | null,
  "compliance_disclosed": true/false,
  "risk_keywords": [],
  "confidence": 0~1 的小数,
  "needs_review": true/false
}
不要输出 JSON 以外的任何内容。"""


def extract(task_type: str, task_payload: dict, transcript: str) -> dict:
    if task_type == "vote":
        system = VOTE_SYSTEM
        user = (
            f"投票议题：{task_payload.get('motion_title', '')}\n"
            f"候选选项：{[o['label'] for o in task_payload.get('options', [])]}\n\n"
            f"=== 通话文字稿 ===\n{transcript}"
        )
    elif task_type == "collection":
        system = COLLECTION_SYSTEM
        user = (
            f"欠费金额：{task_payload.get('amount')}\n"
            f"欠费月份：{task_payload.get('months', '')}\n\n"
            f"=== 通话文字稿 ===\n{transcript}"
        )
    else:
        raise ValueError(f"unknown task_type: {task_type}")

    resp = _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = resp.choices[0].message.content or "{}"
    fields = json.loads(content)
    return {
        "fields": fields,
        "confidence": fields.get("confidence"),
        "needs_review": bool(fields.get("needs_review")),
        "model": _MODEL,
    }
