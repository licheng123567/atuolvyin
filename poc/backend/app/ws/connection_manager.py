# poc/backend/app/ws/connection_manager.py
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # call_id -> {ws: role}
        self._rooms: dict[int, dict[WebSocket, str]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, call_id: int, ws: WebSocket, role: str) -> None:
        async with self._lock:
            self._rooms[call_id][ws] = role

    async def disconnect(self, call_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[call_id].pop(ws, None)
            if not self._rooms[call_id]:
                self._rooms.pop(call_id, None)

    async def broadcast(
        self, call_id: int, message: dict, exclude: WebSocket | None = None
    ) -> None:
        async with self._lock:
            members = list(self._rooms.get(call_id, {}).items())
        for ws, _role in members:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.warning("broadcast failed call=%s: %s", call_id, exc)

    def room_size(self, call_id: int) -> int:
        return len(self._rooms.get(call_id, {}))

    def list_roles(self, call_id: int) -> list[str]:
        return list(self._rooms.get(call_id, {}).values())


_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
