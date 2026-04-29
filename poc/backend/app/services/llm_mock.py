"""LLM mock：返回预设抽取结果。"""


def extract(task_type: str, task_payload: dict, transcript: str) -> dict:
    if task_type == "vote":
        fields = {
            "choice": "同意",
            "reason": "业主表示旧电梯频繁卡顿，明确支持改造",
            "compliance_disclosed": True,
            "confidence": 0.9,
            "needs_review": False,
        }
    elif task_type == "collection":
        fields = {
            "intent": "承诺缴",
            "promise_date": "2026-04-30",
            "excuse_category": "经济困难",
            "compliance_disclosed": True,
            "risk_keywords": [],
            "confidence": 0.85,
            "needs_review": False,
        }
    else:
        fields = {"note": "unknown task_type", "confidence": 0.0, "needs_review": True}

    return {
        "fields": fields,
        "confidence": fields.get("confidence"),
        "needs_review": bool(fields.get("needs_review")),
        "model": "mock",
    }
