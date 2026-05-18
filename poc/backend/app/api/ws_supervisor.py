from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import is_provider_contract_active, should_reveal_owner_phone
from app.risk.supervisor_manager import get_supervisor_manager
from app.ws.auth import decode_ws_token

router = APIRouter()
logger = logging.getLogger(__name__)

_SUPERVISOR_ROLES = {
    "supervisor",
    "admin",
    "project_manager",
}  # Sprint 14.2 — 实时通话墙观察者
# 注：legal 不在此集合 —— 握手快照无案件语境，无法对 legal 算 legal_case_stage；
# 若未来要让 legal 接入，须在 should_reveal_owner_phone 调用处补 legal_case_stage。


@router.websocket("/ws/supervisor")
async def ws_supervisor(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
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
        await websocket.send_json(
            {"type": "error", "code": "ERR_AUTH", "message": "insufficient role"}
        )
        await websocket.close(code=1008)
        return

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "ERR_AUTH", "message": "missing tenant"}
        )
        await websocket.close(code=1008)
        return

    # §9.3 —— 握手时算「该连接能否看明文业主电话」快照。
    # provider_id 为 None = 物业内部，永远明文；非空 = 服务商侧，按合同有效性快照决定。
    # 权衡（见设计文档 §4）：合同有效性只在连接时查一次；中途解约的脱敏延迟到下次重连。
    # 角色重构后所有 token 必带 provider_id；缺失=物业侧是安全默认（fail-open 仅放宽给物业内部）。
    # provider_id_norm: 0 / 缺失 / None 均归一化为 None（物业侧），与 supervisor_scope 口径一致。
    raw_provider_id = payload.get("provider_id")
    provider_id_norm: int | None = int(raw_provider_id) if raw_provider_id else None
    if provider_id_norm is not None and provider_id_norm <= 0:
        provider_id_norm = None

    if provider_id_norm is None:
        can_see_plaintext = True
    else:
        contract_active = is_provider_contract_active(db, tenant_id, provider_id_norm)
        can_see_plaintext = should_reveal_owner_phone(
            role=role,
            provider_id=provider_id_norm,
            contract_active=contract_active,
            project_active=True,  # 广播事件不绑单个项目语境，固定 True
        )

    await websocket.accept()
    manager = get_supervisor_manager()
    await manager.connect(
        tenant_id, websocket, can_see_plaintext=can_see_plaintext, provider_id=provider_id_norm
    )
    logger.info(
        "supervisor connected tenant=%s role=%s plaintext=%s",
        tenant_id,
        role,
        can_see_plaintext,
    )

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
