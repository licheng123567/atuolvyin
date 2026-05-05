from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.risk.supervisor_manager import get_supervisor_manager
from app.ws.auth import decode_ws_token

router = APIRouter()
logger = logging.getLogger(__name__)

_SUPERVISOR_ROLES = {"supervisor", "admin", "platform_super"}


@router.websocket("/ws/supervisor")
async def ws_supervisor(
    websocket: WebSocket,
    token: Annotated[Optional[str], Query()] = None,
):
    payload = decode_ws_token(token or "")
    if payload is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "code": "ERR_AUTH", "message": "invalid token"})
        await websocket.close(code=1008)
        return

    role = payload.get("role", "")
    if role not in _SUPERVISOR_ROLES:
        await websocket.accept()
        await websocket.send_json({"type": "error", "code": "ERR_AUTH", "message": "insufficient role"})
        await websocket.close(code=1008)
        return

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        await websocket.accept()
        await websocket.send_json({"type": "error", "code": "ERR_AUTH", "message": "missing tenant"})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    manager = get_supervisor_manager()
    await manager.connect(tenant_id, websocket)
    logger.info("supervisor connected tenant=%s role=%s", tenant_id, role)

    try:
        while True:
            data = await websocket.receive_text()
            if data == '{"type":"ping"}':
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(tenant_id, websocket)
        logger.info("supervisor disconnected tenant=%s", tenant_id)
