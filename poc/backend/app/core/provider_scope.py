"""v1.5.5 — 服务商权限按「合同 + 项目服务期」双层时效守门。

合同（provider_tenant_contract）= 长期合作框架；
项目（project.plan_end）= 短期服务窗口。

两个 helper：
- active_project_filter：仅返回 active + 服务期内（plan_end NULL 或未过）的项目条件，用于运营查询
- readonly_project_filter：含 active + 30 天内 closed 的项目条件，用于历史报表只读窗口（D2 决策）

返回 SQL 条件元组，调用方用 `.where(*active_project_filter(pid))` 解包。
"""

from __future__ import annotations

import sqlalchemy as sa

from app.models.case import Project

# 到期后服务商保留只读历史的窗口
READONLY_RETENTION_DAYS = 30


def active_project_filter(provider_id: int) -> tuple:
    """服务商可看到的 active 项目条件：归属本服务商 + active + 服务期未过。"""
    return (
        Project.provider_id == provider_id,
        Project.status == "active",
        sa.or_(Project.plan_end.is_(None), Project.plan_end >= sa.func.now()),
    )


def readonly_project_filter(provider_id: int) -> tuple:
    """到期后 30 天内可读历史窗口（仅聚合数据）：active 或 30 天内 closed。"""
    cutoff = sa.func.now() - sa.text(f"interval '{READONLY_RETENTION_DAYS} days'")
    return (
        Project.provider_id == provider_id,
        sa.or_(
            Project.status == "active",
            sa.and_(Project.status == "closed", Project.updated_at >= cutoff),
        ),
    )
