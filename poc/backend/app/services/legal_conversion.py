"""Sprint 16.1 — 法务转化通道核心服务 (PRD §20.4)。

build_case_summary：从 CRM 案件聚合催收时间线 + 推荐处理方式 + 预估法律成本。
撮合律所留 stub（暂不接律所池），订单创建后由平台运营手动 dispatch。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.call import CallRecord
from app.models.case import CollectionCase
from app.models.legal_conversion import LegalServicePackage

# ── recommendation 决策 ─────────────────────────────────────────


_PACKAGE_BY_AMOUNT = [
    # (amount_owed_threshold_yuan, recommended_package_slug, 文案)
    (Decimal("500"), "lawyer_letter", "金额较小，推荐律师函起到威慑即可"),
    (Decimal("3000"), "mediation", "金额中等，推荐诉前调解快速回款"),
    (Decimal("10000"), "small_claims", "金额较大，建议小额诉讼锁定司法保障"),
    (Decimal("99999999"), "full_agency", "金额较高，建议完整代理直至执行"),
]


def recommend_package(
    *,
    amount_owed: Decimal | None,
    months_overdue: int | None,
    contact_count: int,
) -> dict[str, Any]:
    """根据欠费金额 + 逾期月数 + 已联络次数给出推荐。

    返回 {"slug": "...", "reason": "...", "confidence": float}
    """
    amt = amount_owed or Decimal("0")
    base_slug = "lawyer_letter"
    reason = "默认推荐律师函"
    for threshold, slug, text in _PACKAGE_BY_AMOUNT:
        if amt < threshold:
            base_slug = slug
            reason = text
            break

    confidence = 0.6
    if (months_overdue or 0) >= 6:
        confidence += 0.15
    if contact_count >= 5:
        confidence += 0.15
    confidence = min(confidence, 0.95)

    notes: list[str] = []
    if (months_overdue or 0) >= 12:
        notes.append("逾期已超 12 个月，回款难度高")
    if contact_count >= 8:
        notes.append("多次电话催收无果，电话沟通空间已耗尽")

    return {
        "slug": base_slug,
        "reason": reason,
        "confidence": round(confidence, 2),
        "notes": notes,
    }


# ── 历史时间线摘要 ──────────────────────────────────────────────


def build_timeline_summary(db: Session, *, case: CollectionCase) -> dict[str, Any]:
    """聚合该案件的通话历史，生成法务可读摘要（不含明细 PII）。"""
    rows = db.execute(
        select(
            func.count(CallRecord.id),
            func.coalesce(func.sum(CallRecord.duration_sec), 0),
            func.min(CallRecord.started_at),
            func.max(CallRecord.started_at),
        ).where(CallRecord.case_id == case.id)
    ).one()
    total_calls, total_seconds, first_at, last_at = rows

    result_rows = db.execute(
        select(CallRecord.result_tag, func.count(CallRecord.id))
        .where(CallRecord.case_id == case.id, CallRecord.result_tag.isnot(None))
        .group_by(CallRecord.result_tag)
    ).all()
    result_breakdown = {tag: int(c) for tag, c in result_rows}

    return {
        "total_calls": int(total_calls or 0),
        "total_minutes": round(int(total_seconds or 0) / 60, 1),
        "first_contact_at": first_at.isoformat() if first_at else None,
        "last_contact_at": last_at.isoformat() if last_at else None,
        "result_tag_breakdown": result_breakdown,
        "stage": case.stage,
        "amount_owed": float(case.amount_owed) if case.amount_owed else None,
        "months_overdue": case.months_overdue,
    }


# ── 法律成本预估 ────────────────────────────────────────────────


def estimate_cost(
    *,
    package: LegalServicePackage,
    amount_owed: Decimal | None,
) -> dict[str, Any]:
    """给出服务包的报价 + 预估法律成本 + 预估回款概率。"""
    amt = amount_owed or Decimal("0")
    # 预估回款概率：按服务包类型给经验值（后续可换成历史数据回归）
    recovery_prob = {
        "lawyer_letter": 0.32,
        "mediation": 0.55,
        "small_claims": 0.72,
        "full_agency": 0.85,
    }.get(package.package_type, 0.40)

    extra_court_fee = Decimal("0")
    if package.package_type == "small_claims":
        # 小额诉讼受理费 ≈ 标的额 × 2.5%（最低 50）
        extra_court_fee = max(amt * Decimal("0.025"), Decimal("50"))
    elif package.package_type == "full_agency":
        extra_court_fee = max(amt * Decimal("0.05"), Decimal("100"))

    total_estimate = package.price + extra_court_fee
    expected_recovery = amt * Decimal(str(recovery_prob))

    return {
        "service_fee": float(package.price),
        "court_fee_estimate": float(extra_court_fee),
        "total_cost_estimate": float(total_estimate),
        "expected_recovery_amount": float(round(expected_recovery, 2)),
        "recovery_probability": recovery_prob,
        "net_estimate": float(round(expected_recovery - total_estimate, 2)),
    }
