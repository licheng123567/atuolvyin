# poc/backend/app/api/ws_calls.py
from __future__ import annotations

import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.call import CallRecord
from app.ws.auth import decode_ws_token
from app.ws.call_session import CallSession
from app.ws.connection_manager import get_connection_manager

router = APIRouter()
logger = logging.getLogger(__name__)


# In-process registry: call_id -> CallSession (one per active call)
_sessions: dict[int, CallSession] = {}


def _authorize(payload: dict, role: str, call: CallRecord) -> bool:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    user_role = payload.get("role", "")

    if call.tenant_id != tenant_id:
        return False

    if role == "agent":
        return call.caller_user_id == user_id
    if role == "observer":
        return user_role in {"admin", "supervisor"}
    return False


@router.websocket("/ws/calls/{call_id}")
async def ws_calls(
    websocket: WebSocket,
    call_id: int,
    token: Annotated[Optional[str], Query()] = None,
    role: Annotated[str, Query()] = "agent",
    db: Annotated[Session, Depends(get_db)] = None,
):
    payload = decode_ws_token(token or "")
    if payload is None:
        await websocket.close(code=1008, reason="invalid token")
        return

    call = db.execute(
        select(CallRecord).where(CallRecord.id == call_id)
    ).scalar_one_or_none()
    if not call:
        await websocket.close(code=1008, reason="call not found")
        return

    if not _authorize(payload, role, call):
        await websocket.close(code=1008, reason="policy violation")
        return

    await websocket.accept()
    manager = get_connection_manager()
    await manager.connect(call_id, websocket, role)

    # Lazy-init the call session on first agent connection
    session = _sessions.get(call_id)
    if session is None and role == "agent":
        async def broadcast_transcript(msg: dict) -> None:
            await manager.broadcast(call_id, msg)

        async def broadcast_suggestion(msg: dict) -> None:
            await manager.broadcast(call_id, msg)

        async def broadcast_tag(tag: dict) -> None:
            await manager.broadcast(call_id, {"type": "tag.ready", **tag})

        session = CallSession(
            call_id=call_id,
            on_transcript_broadcast=broadcast_transcript,
            on_suggestion_broadcast=broadcast_suggestion,
            on_tag_ready=broadcast_tag,
        )
        await session.start(db)
        _sessions[call_id] = session

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"] is not None:
                if role == "agent" and session:
                    await session.feed_audio(msg["bytes"])
                continue
            if "text" in msg and msg["text"] is not None:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                t = data.get("type")
                if t == "ping":
                    await websocket.send_json({"type": "pong"})
                elif t == "call.started" and role == "agent":
                    call.status = "live"
                    db.commit()
                elif t == "call.ended" and role == "agent":
                    call.status = "live_ended_pending_analysis"
                    db.commit()
                    if session:
                        await session.stop()
                elif t == "suggestion.feedback" and role == "agent":
                    # Persisted via separate REST endpoint (T15); WS just acks for UX
                    await websocket.send_json({"type": "ack", "for": data.get("id")})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(call_id, websocket)
        # Tear down session if room empty
        if manager.room_size(call_id) == 0:
            sess = _sessions.pop(call_id, None)
            if sess:
                await sess.stop()
