"""Sprint 14.3 — 用户偏好读写 (PRD §8.2)。

GET   /api/v1/users/me/preferences  — 任何认证用户
PATCH /api/v1/users/me/preferences  — merge 局部更新

当前已知 keys：
  - app_intro_dismissed: bool — 首次登录引导 modal 是否已关闭
  - 其他 UI 偏好按需扩展
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.db import get_db
from app.core.security import get_token_payload
from app.models.user import UserAccount

router = APIRouter()


class PreferencesOut(BaseModel):
    preferences: dict[str, Any]


class PreferencesPatch(BaseModel):
    preferences: dict[str, Any]


def _require_user_id(payload: dict) -> int:
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少 user_id"},
        )
    return user_id


@router.get("/me/preferences", response_model=PreferencesOut)
def get_my_preferences(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> PreferencesOut:
    user_id = _require_user_id(payload)
    user = db.get(UserAccount, user_id)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    return PreferencesOut(preferences=dict(user.preferences or {}))


@router.patch("/me/preferences", response_model=PreferencesOut)
def patch_my_preferences(
    body: PreferencesPatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> PreferencesOut:
    user_id = _require_user_id(payload)
    user = db.get(UserAccount, user_id)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    merged = dict(user.preferences or {})
    merged.update(body.preferences)
    user.preferences = merged
    flag_modified(user, "preferences")
    db.commit()
    db.refresh(user)
    return PreferencesOut(preferences=dict(user.preferences or {}))
