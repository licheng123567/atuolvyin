from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import get_current_user, get_token_payload
from app.models.user import UserAccount
from app.schemas.user import UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(get_current_user)],
) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        name=user.name,
        role=payload.get("role", ""),
        tenant_id=payload.get("tenant_id"),
        scope=payload.get("scope", ""),
    )
