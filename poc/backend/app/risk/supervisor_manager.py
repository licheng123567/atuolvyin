from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class SupervisorManager:
    """In-process WebSocket pool for supervisor clients, keyed by tenant_id."""

    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[tenant_id].add(ws)

    async def disconnect(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[tenant_id].discard(ws)
            if not self._rooms[tenant_id]:
                self._rooms.pop(tenant_id, None)

    async def broadcast(self, tenant_id: int, event: dict) -> None:
        async with self._lock:
            members = list(self._rooms.get(tenant_id, set()))
        for ws in members:
            try:
                await ws.send_json(event)
            except Exception as exc:
                logger.warning("supervisor broadcast failed tenant=%s: %s", tenant_id, exc)
                await self.disconnect(tenant_id, ws)


_supervisor_manager: Optional[SupervisorManager] = None


def get_supervisor_manager() -> SupervisorManager:
    global _supervisor_manager
    if _supervisor_manager is None:
        _supervisor_manager = SupervisorManager()
    return _supervisor_manager
