"""v2.2 — 缴费链接生成 + 审计记录（坐席端 / 物业管理端共用）。

坐席端（agent_cases）与物业管理端（admin_cases）的「发送缴费链接」共用同一套
短链生成 + audit log 逻辑；鉴权 / 案件归属校验由各端点自行负责。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from secrets import token_urlsafe

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import mask_phone
from app.models.case import CollectionCase, OwnerProfile
from app.models.discount_offer import DiscountOffer
from app.models.payment_link import PaymentLink
from app.services.audit import log_audit


class PaymentBreakdown(BaseModel):
    """业主缴费明细构成：应缴 − 已减免 = 应支付。"""

    principal: Decimal | None
    late_fee: Decimal | None
    original: Decimal
    waived: Decimal
    payable: Decimal
    has_pending: bool


def compute_payable(db: Session, case: CollectionCase) -> PaymentBreakdown:
    """算案件当前应付额。

    已减免 = 该案件 status='approved' 且未过期的 DiscountOffer（多条取 approved_at 最新）。
    pending 减免不抵扣，但置 has_pending=True 供前端提示。
    """
    original = case.amount_owed or Decimal("0")
    now = datetime.now(UTC)

    active_offer = (
        db.execute(
            select(DiscountOffer)
            .where(
                DiscountOffer.tenant_id == case.tenant_id,
                DiscountOffer.case_id == case.id,
                DiscountOffer.status == "approved",
                DiscountOffer.expires_at > now,
            )
            .order_by(DiscountOffer.approved_at.desc().nullslast(), DiscountOffer.id.desc())
        )
        .scalars()
        .first()
    )
    if active_offer is not None:
        payable = active_offer.proposed_amount
        waived = original - payable
    else:
        payable = original
        waived = Decimal("0")

    has_pending = (
        db.execute(
            select(DiscountOffer.id).where(
                DiscountOffer.tenant_id == case.tenant_id,
                DiscountOffer.case_id == case.id,
                DiscountOffer.status.in_(("pending_supervisor", "pending_admin")),
            )
        ).first()
        is not None
    )

    return PaymentBreakdown(
        principal=case.principal_amount,
        late_fee=case.late_fee_amount,
        original=original,
        waived=waived,
        payable=payable,
        has_pending=has_pending,
    )


class PaymentLinkOut(BaseModel):
    case_id: int
    token: str
    link: str
    short_link: str
    sent_to: str  # masked phone
    sent_at: datetime
    expires_at: datetime
    sms_status: str  # "queued" / "sent" / "skipped"
    breakdown: PaymentBreakdown


def build_and_record_payment_link(
    db: Session,
    *,
    case: CollectionCase,
    owner: OwnerProfile,
    actor_user_id: int,
    actor_role: str,
    tenant_id: int,
) -> PaymentLinkOut:
    """生成缴费短链、写 payment_link 行 + audit log，返回链接与支付明细。

    调用方需先完成：案件归属校验 / owner 存在性校验 / 鉴权。

    注意：本函数内部执行 db.commit() —— 会顺带提交调用方在同一 Session 中
    已写入但未提交的行。调用方应在完成自身写操作后、作为最后一步调用本函数。
    """

    token = token_urlsafe(12)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=7)
    full_link = f"https://pay.youcuihuicui.com/c/{token}"
    short_link = f"https://yzhc.cn/p/{token[:8]}"  # 8 字符展示前缀；完整 token 入库为权威标识
    sent_to_masked = mask_phone(owner.phone_enc)

    db.add(
        PaymentLink(
            token=token,
            tenant_id=tenant_id,
            case_id=case.id,
            project_id=case.project_id,
            created_by_user_id=actor_user_id,
            payment_mode="property_self",
            expires_at=expires_at,
        )
    )

    breakdown = compute_payable(db, case)

    log_audit(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        tenant_id=tenant_id,
        action="case.payment_link_sent",
        target_type="collection_case",
        target_id=case.id,
        payload={
            "owner_phone_masked": sent_to_masked,
            "amount": str(case.amount_owed) if case.amount_owed else None,
            "payable": str(breakdown.payable),
            "token": token,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()

    return PaymentLinkOut(
        case_id=case.id,
        token=token,
        link=full_link,
        short_link=short_link,
        sent_to=sent_to_masked,
        sent_at=now,
        expires_at=expires_at,
        sms_status="queued",
        breakdown=breakdown,
    )
