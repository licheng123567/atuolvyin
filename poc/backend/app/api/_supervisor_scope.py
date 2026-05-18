"""共享 Supervisor scope helper。

物业侧督导（provider_id=None）vs 服务商侧督导（provider_id 非空）的案件
/ 团队成员可见性过滤，供 /supervisor/* 端点复用。

范例参照 app/api/provider_legal.py 的 _ctx / _provider_legal_case_filter。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select

from app.core.security import get_token_payload
from app.models.case import CollectionCase, Project
from app.models.tenant import UserTenantMembership


@dataclass(frozen=True)
class SupervisorScope:
    tenant_id: int
    provider_id: int | None  # None=物业侧督导；非 None=服务商侧督导


def supervisor_scope(payload: Annotated[dict, Depends(get_token_payload)]) -> SupervisorScope:
    """从 token 解析督导 scope。可作 FastAPI 依赖直接注入。"""
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_SCOPE", "message": "需要租户上下文"},
        )
    raw_provider = payload.get("provider_id")
    provider_id: int | None = None
    if raw_provider is not None:
        provider_id = int(raw_provider)
        if provider_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ERR_NO_SCOPE", "message": "provider 上下文非法"},
            )
    return SupervisorScope(
        tenant_id=int(tenant_id),
        provider_id=provider_id,
    )


def _provider_projects(scope: SupervisorScope) -> Select[tuple[int]]:
    """子查询：本 scope 下的项目 id 集。"""
    q = select(Project.id).where(Project.tenant_id == scope.tenant_id)
    if scope.provider_id is None:
        return q.where(Project.provider_id.is_(None))
    return q.where(Project.provider_id == scope.provider_id)


def supervisor_case_filter(scope: SupervisorScope) -> sa.ColumnElement[bool]:
    """案件可见性；返回针对 ``CollectionCase`` 的过滤表达式。

    调用方需在查询中 select/join ``CollectionCase``，本函数不负责 join。

    物业督导：无项目案件 + 物业项目案件（project.provider_id IS NULL）。
    服务商督导：仅本服务商项目案件。

    注：SQL NOT IN 三值逻辑陷阱 — 当 project_id IS NULL 时，
    ``CollectionCase.project_id.not_in(subquery)`` 求值为 UNKNOWN（非 TRUE），
    导致无项目案件被静默排除。物业侧分支改用显式 OR 子句处理 NULL 行。
    """
    if scope.provider_id is None:
        # 所有服务商项目的 id 集（用于排除）
        provider_project_ids = select(Project.id).where(
            Project.tenant_id == scope.tenant_id,
            Project.provider_id.is_not(None),
        )
        return sa.and_(
            CollectionCase.tenant_id == scope.tenant_id,
            sa.or_(
                # 无项目案件（project_id IS NULL），NOT IN 会把 NULL 排除，需显式处理
                CollectionCase.project_id.is_(None),
                # 物业自办项目案件（project_id 不在服务商项目集内）
                CollectionCase.project_id.not_in(provider_project_ids),
            ),
        )
    return sa.and_(
        CollectionCase.tenant_id == scope.tenant_id,
        CollectionCase.project_id.in_(_provider_projects(scope)),
    )


def supervisor_agent_filter(scope: SupervisorScope) -> sa.ColumnElement[bool]:
    """团队成员（催收员）可见性；返回针对 ``UserTenantMembership`` 的过滤表达式。

    调用方需在查询中 select/join ``UserTenantMembership``，本函数不负责 join。
    """
    base = sa.and_(
        UserTenantMembership.tenant_id == scope.tenant_id,
        UserTenantMembership.role == "agent",
    )
    if scope.provider_id is None:
        return sa.and_(base, UserTenantMembership.provider_id.is_(None))
    return sa.and_(base, UserTenantMembership.provider_id == scope.provider_id)
