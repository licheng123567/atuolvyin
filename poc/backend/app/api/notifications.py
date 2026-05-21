"""Sprint 15.4 — 站内信 REST API (PRD §L412)。

GET   /api/v1/users/me/notifications        — 列出当前用户站内信
GET   /api/v1/users/me/notifications/unread-count
PATCH /api/v1/users/me/notifications/{id}/read
PATCH /api/v1/users/me/notifications/read-all
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload
from app.models.notification import Notification

router = APIRouter()


class NotificationItem(BaseModel):
    id: int
    event_type: str
    severity: str
    title: str
    body: str
    payload: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationsListResp(BaseModel):
    items: list[NotificationItem]
    total: int


class UnreadCountResp(BaseModel):
    unread: int


def _require_user_id(payload: dict) -> int:
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少 user_id"},
        )
    return user_id


@router.get("/me/notifications", response_model=NotificationsListResp)
def list_my_notifications(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    only_unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    # v0.6.0 — event_type 多值过滤(如 `&event_type=promise_expiring&event_type=supervisor_action`)
    event_type: list[str] | None = Query(None),
) -> NotificationsListResp:
    user_id = _require_user_id(payload)
    q = select(Notification).where(Notification.user_id == user_id)
    if only_unread:
        q = q.where(Notification.read_at.is_(None))
    if event_type:
        q = q.where(Notification.event_type.in_(event_type))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    total_q = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    if event_type:
        total_q = total_q.where(Notification.event_type.in_(event_type))
    total = db.execute(total_q).scalar_one()
    return NotificationsListResp(
        items=[
            NotificationItem(
                id=n.id,
                event_type=n.event_type,
                severity=n.severity,
                title=n.title,
                body=n.body,
                payload=n.payload,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n in rows
        ],
        total=int(total),
    )


@router.get("/me/notifications/unread-count", response_model=UnreadCountResp)
def my_unread_count(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> UnreadCountResp:
    user_id = _require_user_id(payload)
    cnt = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    ).scalar_one()
    return UnreadCountResp(unread=int(cnt))


@router.patch(
    "/me/notifications/{notif_id}/read",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def mark_read(
    notif_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    user_id = _require_user_id(payload)
    n = db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == user_id,
        )
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通知不存在"},
        )
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.patch(
    "/me/notifications/read-all",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def mark_all_read(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    user_id = _require_user_id(payload)
    db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
