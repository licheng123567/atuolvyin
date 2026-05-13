"""Sprint 16.3 — 律所→平台介绍费账单生成服务 (PRD §20.4)。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.legal_conversion import LegalConversionOrder
from app.models.legal_platform_invoice import LegalPlatformInvoice


def aggregate_completed_orders(
    db: Session,
    *,
    law_firm_id: int,
    period_start: datetime,
    period_end: datetime,
) -> tuple[Decimal, list[dict]]:
    """聚合该律所在 [period_start, period_end) 内已完成订单的 platform_fee。

    返回 (total_fee, line_items)。line_items 是面向账单的精简快照。
    """
    rows = db.execute(
        select(
            LegalConversionOrder.id,
            LegalConversionOrder.case_id,
            LegalConversionOrder.package_id,
            LegalConversionOrder.price_quoted,
            LegalConversionOrder.platform_fee_amount,
            LegalConversionOrder.completed_at,
        )
        .where(
            LegalConversionOrder.law_firm_id == law_firm_id,
            LegalConversionOrder.status == "completed",
            LegalConversionOrder.completed_at >= period_start,
            LegalConversionOrder.completed_at < period_end,
        )
        .order_by(LegalConversionOrder.completed_at)
    ).all()

    lines: list[dict] = []
    total = Decimal("0")
    for r in rows:
        total += r.platform_fee_amount or Decimal("0")
        lines.append(
            {
                "order_id": int(r.id),
                "case_id": int(r.case_id),
                "package_id": int(r.package_id),
                "price_quoted": float(r.price_quoted),
                "platform_fee": float(r.platform_fee_amount),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
        )
    return total, lines


def generate_invoice(
    db: Session,
    *,
    law_firm_id: int,
    period_start: datetime,
    period_end: datetime,
) -> tuple[LegalPlatformInvoice, bool]:
    """生成 / 返回该律所对应账期的账单。

    返回 (invoice, created)。created=False 表示账单已存在（幂等）。
    """
    existing = db.execute(
        select(LegalPlatformInvoice).where(
            LegalPlatformInvoice.law_firm_id == law_firm_id,
            LegalPlatformInvoice.period_start == period_start,
            LegalPlatformInvoice.period_end == period_end,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    total, lines = aggregate_completed_orders(
        db,
        law_firm_id=law_firm_id,
        period_start=period_start,
        period_end=period_end,
    )

    invoice = LegalPlatformInvoice(
        law_firm_id=law_firm_id,
        period_start=period_start,
        period_end=period_end,
        total_amount=total,
        order_count=len(lines),
        invoice_lines=lines,
        status="DRAFT",
    )
    db.add(invoice)
    db.flush()
    return invoice, True


def total_unpaid_fee(db: Session, *, law_firm_id: int) -> Decimal:
    """律所所有 CONFIRMED 但未 PAID 的账单合计金额。"""
    val = db.execute(
        select(func.coalesce(func.sum(LegalPlatformInvoice.total_amount), 0)).where(
            LegalPlatformInvoice.law_firm_id == law_firm_id,
            LegalPlatformInvoice.status == "CONFIRMED",
        )
    ).scalar_one()
    return Decimal(str(val))
