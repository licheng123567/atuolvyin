"""LLM dispatcher：mock 或 OpenAI 兼容 API（DeepSeek / Ollama / Qwen 共用）。"""
from app.core.config import settings


def extract(task_type: str, task_payload: dict, transcript: str) -> dict:
    backend = settings.llm_backend.lower()
    if backend == "mock":
        from . import llm_mock as impl
        return impl.extract(task_type, task_payload, transcript)
    if backend == "api":
        from . import llm_openai_compatible as impl
        return impl.extract(task_type, task_payload, transcript)
    raise RuntimeError(f"unknown LLM_BACKEND: {settings.llm_backend}")
