"""§9.2 — 佣金计算共用逻辑。

收口两处佣金端点（物业内勤 admin.py / 服务商 provider_admin.py）的：
- 「实收金额」推导（扣已执行减免）；
- 「按项目佣金率」解析（D1 内勤率 / D2 服务商率，NULL 回退系统默认）。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Project
from app.models.discount_offer import DiscountOffer

DEFAULT_COMMISSION_RATE = Decimal("0.05")


def executed_discount_amounts(
    db: Session, tenant_id: int, case_ids: list[int]
) -> dict[int, Decimal]:
    """case_id → 业主实收额，仅含有 status='executed' 减免的案件。

    tenant_id：按 tenant_id 限定租户范围，确保多租户隔离并命中
    ix_discount_offer_tenant_status 复合索引。
    §9.2-C：减免部分不计佣金 —— 已执行减免的案件，实收 = 该减免的
    proposed_amount（业主实际缴的钱）。无已执行减免的案件不在返回 dict 内，
    调用方回退 amount_owed。多条 executed（罕见）→ 按 id 升序遍历，最新 id 胜出。
    """
    if not case_ids:
        return {}
    rows = db.execute(
        select(DiscountOffer.case_id, DiscountOffer.proposed_amount)
        .where(
            DiscountOffer.tenant_id == tenant_id,
            DiscountOffer.case_id.in_(case_ids),
            DiscountOffer.status == "executed",
        )
        .order_by(DiscountOffer.id)
    ).all()
    result: dict[int, Decimal] = {}
    for case_id, proposed_amount in rows:
        result[case_id] = Decimal(str(proposed_amount or 0))
    return result


def internal_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D1：项目级内勤佣金率；NULL / 无项目 → 系统默认 0.05。"""
    if project is not None and project.internal_agent_commission_rate is not None:
        return Decimal(str(project.internal_agent_commission_rate))
    return DEFAULT_COMMISSION_RATE


def provider_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D2：项目级服务商催收员佣金率；NULL / 无项目 → 系统默认 0.05。"""
    if project is not None and project.provider_agent_commission_rate is not None:
        return Decimal(str(project.provider_agent_commission_rate))
    return DEFAULT_COMMISSION_RATE
