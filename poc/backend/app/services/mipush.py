"""MiPush dispatcher — Xiaomi HTTP API in production, in-memory mock for tests."""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class MiPushClient(Protocol):
    sent_messages: list  # only present on mock

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None: ...


_singleton: MiPushClient | None = None


def get_mipush_client() -> MiPushClient:
    global _singleton
    if _singleton is not None:
        return _singleton
    backend = settings.mipush_backend.lower()
    if backend == "mock":
        from .mipush_mock import MockMiPushClient

        _singleton = MockMiPushClient()
    elif backend == "xiaomi":
        from .mipush_xiaomi import XiaomiMiPushClient

        _singleton = XiaomiMiPushClient(
            app_secret=settings.mipush_app_secret,
            package_name=settings.mipush_package_name,
        )
    else:
        raise RuntimeError(f"unknown MIPUSH_BACKEND: {settings.mipush_backend}")
    return _singleton


def _reset_for_tests() -> None:
    """Internal: reset the singleton between tests."""
    global _singleton
    _singleton = None


def _get_mock_sent() -> list[dict]:
    """Return the sent_messages list from the current mock singleton (for test assertions)."""
    global _singleton
    if _singleton is None:
        return []
    if not hasattr(_singleton, "sent_messages"):
        raise RuntimeError("_get_mock_sent() called but current backend is not mock")
    return _singleton.sent_messages  # type: ignore[attr-defined]
