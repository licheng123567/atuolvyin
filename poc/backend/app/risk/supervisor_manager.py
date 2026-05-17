from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from fastapi import WebSocket

from app.core.phone_visibility import display_owner_phone

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SupervisorConn:
    """单个 supervisor WS 连接的身份快照。WS 握手时算一次，连接生命周期内不变。"""

    can_see_plaintext: bool


class SupervisorManager:
    """In-process WebSocket pool for supervisor clients, keyed by tenant_id.

    §9.3 —— 每个连接在握手时算出 can_see_plaintext 快照存进 SupervisorConn；
    broadcast 收到 owner_phone_enc 密文时，按每个连接的快照逐一注入
    owner_phone_masked（明文 / 脱敏）。
    """

    def __init__(self) -> None:
        self._rooms: dict[int, dict[WebSocket, SupervisorConn]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(
        self, tenant_id: int, ws: WebSocket, *, can_see_plaintext: bool
    ) -> None:
        async with self._lock:
            self._rooms[tenant_id][ws] = SupervisorConn(can_see_plaintext=can_see_plaintext)

    async def disconnect(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(tenant_id)
            if room is not None:
                room.pop(ws, None)
                if not room:
                    self._rooms.pop(tenant_id, None)

    async def broadcast(
        self,
        tenant_id: int,
        event: dict,
        *,
        owner_phone_enc: str | None = None,
    ) -> None:
        """向 tenant 房间群发 event。

        owner_phone_enc 非空时，按每个连接的 can_see_plaintext 快照逐一注入
        owner_phone_masked（覆盖 event 里同名键）；为空时 event 原样下发。
        """
        async with self._lock:
            members = list(self._rooms.get(tenant_id, {}).items())
        for ws, conn in members:
            try:
                if owner_phone_enc is not None:
                    payload = {
                        **event,
                        "owner_phone_masked": display_owner_phone(
                            owner_phone_enc, reveal=conn.can_see_plaintext
                        ),
                    }
                else:
                    payload = event
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning("supervisor broadcast failed tenant=%s: %s", tenant_id, exc)
                await self.disconnect(tenant_id, ws)


_supervisor_manager: SupervisorManager | None = None


def get_supervisor_manager() -> SupervisorManager:
    global _supervisor_manager
    if _supervisor_manager is None:
        _supervisor_manager = SupervisorManager()
    return _supervisor_manager
