"""seed_demo.py — 幂等 Demo 数据 seed 脚本.

用法:
    docker exec autoluyin-backend python -m scripts.seed_demo

重复运行安全（已存在则跳过）。
"""
from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import select

from datetime import date, datetime, timedelta, timezone

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.models.case import CollectionCase, OwnerProfile
from app.models.discount_offer import DiscountOffer
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.law_firm_membership import LawFirmMembership
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.models.risk import RiskKeyword
from app.models.script import ScriptTemplate
from app.models.settlement import SettlementStatement
from app.models.settings import TenantSettings
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    Tenant,
    UserTenantMembership,
)
from app.models.user import UserAccount

DEMO_PASSWORD = "Demo@123!"


def _upsert_tenant(db) -> Tenant:
    # 优先按 credit_code，其次按名称（兼容历史 demo 数据有不同 credit_code 的情况）
    existing = db.execute(
        select(Tenant).where(Tenant.credit_code == "DEMO000000000001")
    ).scalar_one_or_none()
    if existing is None:
        existing = db.execute(
            select(Tenant).where(Tenant.name == "Demo 物业").order_by(Tenant.id)
        ).scalars().first()
    if existing:
        print(f"[exists] Tenant: Demo 物业  id={existing.id}")
        return existing
    tenant = Tenant(
        name="Demo 物业",
        credit_code="DEMO000000000001",
        admin_phone_enc=encrypt_phone("13000000002"),
        plan="trial",
        monthly_minute_quota=600,
        is_active=True,
    )
    db.add(tenant)
    db.flush()
    print(f"[created] Tenant: Demo 物业  id={tenant.id}")
    return tenant


def _upsert_user(db, phone: str, name: str) -> tuple[UserAccount, bool]:
    """Return (user, created)."""
    enc = encrypt_phone(phone)
    existing = db.execute(
        select(UserAccount).where(UserAccount.phone_enc == enc)
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  UserAccount: {name} ({phone})")
        return existing, False
    user = UserAccount(
        phone_enc=enc,
        name=name,
        password_hash=get_password_hash(DEMO_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    print(f"[created] UserAccount: {name} ({phone})  id={user.id}")
    return user, True


def _upsert_membership(
    db,
    user: UserAccount,
    tenant: Tenant,
    role: str,
    *,
    provider_id: int | None = None,
) -> None:
    # 同一 user 在同一 tenant 可能有多条 membership（如同时是督导+催收+协调员）
    existing = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant.id,
            UserTenantMembership.role == role,
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  Membership: {user.name} -> {role}")
        return
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=role,
        source_type="INTERNAL",
        provider_id=provider_id,
        is_active=True,
    )
    db.add(membership)
    db.flush()
    suffix = f"  provider_id={provider_id}" if provider_id else ""
    print(f"[created] Membership: {user.name} -> {role}  tenant_id={tenant.id}{suffix}")


def _upsert_provider(db) -> ServiceProvider:
    existing = db.execute(
        select(ServiceProvider).where(ServiceProvider.name == "Demo 法务公司")
    ).scalar_one_or_none()
    if existing:
        print("[exists]  ServiceProvider: Demo 法务公司")
        return existing
    provider = ServiceProvider(
        name="Demo 法务公司",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13000000010"),
        monthly_minute_quota=1000,
        is_active=True,
        audit_status="approved",
        audit_at=datetime.now(timezone.utc),
        contact_email="contact@demo-legal.example.com",
        description="演示用第三方法务/外包催收公司",
    )
    db.add(provider)
    db.flush()
    print(f"[created] ServiceProvider: Demo 法务公司  id={provider.id}")
    return provider


def _upsert_provider_contract(
    db, tenant: Tenant, provider: ServiceProvider
) -> ProviderTenantContract:
    existing = db.execute(
        select(ProviderTenantContract).where(
            ProviderTenantContract.tenant_id == tenant.id,
            ProviderTenantContract.provider_id == provider.id,
        )
    ).scalar_one_or_none()
    if existing:
        print(
            f"[exists]  ProviderTenantContract: tenant={tenant.id} provider={provider.id}"
        )
        return existing
    now = datetime.now(timezone.utc)
    contract = ProviderTenantContract(
        tenant_id=tenant.id,
        provider_id=provider.id,
        signed_at=now - timedelta(days=30),
        expires_at=now + timedelta(days=365),
        service_types=["legal", "collection"],
        status="active",
    )
    db.add(contract)
    db.flush()
    print(f"[created] ProviderTenantContract: id={contract.id}")
    return contract


def _upsert_settlement(db, contract: ProviderTenantContract) -> None:
    existing = db.execute(
        select(SettlementStatement).where(
            SettlementStatement.contract_id == contract.id
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  SettlementStatement: contract_id={contract.id}")
        return
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    statement = SettlementStatement(
        contract_id=contract.id,
        period_start=period_start - timedelta(days=30),
        period_end=period_start - timedelta(seconds=1),
        total_amount=Decimal("8800.00"),
        status="DRAFT",
    )
    db.add(statement)
    db.flush()
    print(f"[created] SettlementStatement: id={statement.id}")


def _upsert_owner(db, tenant: Tenant, name: str, phone: str, building: str, room: str) -> OwnerProfile:
    enc = encrypt_phone(phone)
    existing = db.execute(
        select(OwnerProfile).where(
            OwnerProfile.tenant_id == tenant.id,
            OwnerProfile.phone_enc == enc,
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  OwnerProfile: {name}")
        return existing
    owner = OwnerProfile(
        tenant_id=tenant.id,
        name=name,
        phone_enc=enc,
        building=building,
        room=room,
        tags=[],
        do_not_call=False,
    )
    db.add(owner)
    db.flush()
    print(f"[created] OwnerProfile: {name}  id={owner.id}")
    return owner


def _upsert_project(
    db,
    tenant: Tenant,
    name: str,
    property_pm_user_id: int | None = None,
    provider_id: int | None = None,
    provider_pm_user_id: int | None = None,
    description: str | None = None,
    # v1.6 — 收费 + 合同
    charge_rate_per_sqm: Decimal | None = None,
    charge_rate_text: str | None = None,
    charge_period: str | None = None,
    contract_type: str | None = None,
    contract_start_date: date | None = None,
    contract_end_date: date | None = None,
    charge_notes: str | None = None,
    # v1.6.1 — 项目级减免覆盖（None = 继承租户）
    discount_auto_approve_threshold_pct: int | None = None,
    discount_supervisor_max_pct: int | None = None,
    discount_disabled: bool | None = None,
    # v1.6.2 — 项目级滞纳金减免覆盖
    late_fee_waive_auto_approve_threshold_pct: int | None = None,
    late_fee_waive_supervisor_max_pct: int | None = None,
    late_fee_waive_disabled: bool | None = None,
):
    from app.models.case import Project as ProjectModel
    existing = db.execute(
        select(ProjectModel).where(
            ProjectModel.tenant_id == tenant.id,
            ProjectModel.name == name,
        )
    ).scalar_one_or_none()
    if existing:
        # 已存在则补关键字段（含 v1.6 / v1.6.1 字段）
        if existing.property_pm_user_id is None and property_pm_user_id:
            existing.property_pm_user_id = property_pm_user_id
        if existing.provider_id is None and provider_id:
            existing.provider_id = provider_id
        if existing.provider_pm_user_id is None and provider_pm_user_id:
            existing.provider_pm_user_id = provider_pm_user_id
        if existing.charge_rate_per_sqm is None and charge_rate_per_sqm is not None:
            existing.charge_rate_per_sqm = charge_rate_per_sqm
        if existing.charge_period is None and charge_period:
            existing.charge_period = charge_period
        if existing.contract_type is None and contract_type:
            existing.contract_type = contract_type
        if existing.contract_start_date is None and contract_start_date:
            existing.contract_start_date = contract_start_date
        if existing.contract_end_date is None and contract_end_date:
            existing.contract_end_date = contract_end_date
        if existing.charge_notes is None and charge_notes:
            existing.charge_notes = charge_notes
        if existing.discount_auto_approve_threshold_pct is None and discount_auto_approve_threshold_pct is not None:
            existing.discount_auto_approve_threshold_pct = discount_auto_approve_threshold_pct
        if existing.discount_supervisor_max_pct is None and discount_supervisor_max_pct is not None:
            existing.discount_supervisor_max_pct = discount_supervisor_max_pct
        if existing.discount_disabled is None and discount_disabled is not None:
            existing.discount_disabled = discount_disabled
        if existing.charge_rate_text is None and charge_rate_text:
            existing.charge_rate_text = charge_rate_text
        if getattr(existing, "late_fee_waive_auto_approve_threshold_pct", None) is None and late_fee_waive_auto_approve_threshold_pct is not None:
            existing.late_fee_waive_auto_approve_threshold_pct = late_fee_waive_auto_approve_threshold_pct
        if getattr(existing, "late_fee_waive_supervisor_max_pct", None) is None and late_fee_waive_supervisor_max_pct is not None:
            existing.late_fee_waive_supervisor_max_pct = late_fee_waive_supervisor_max_pct
        if getattr(existing, "late_fee_waive_disabled", None) is None and late_fee_waive_disabled is not None:
            existing.late_fee_waive_disabled = late_fee_waive_disabled
        print(f"[exists]  Project: {name}  id={existing.id}")
        return existing
    p = ProjectModel(
        tenant_id=tenant.id,
        name=name,
        property_pm_user_id=property_pm_user_id,
        provider_id=provider_id,
        provider_pm_user_id=provider_pm_user_id,
        description=description,
        status="active",
        charge_rate_per_sqm=charge_rate_per_sqm,
        charge_rate_text=charge_rate_text,
        charge_period=charge_period,
        contract_type=contract_type,
        contract_start_date=contract_start_date,
        contract_end_date=contract_end_date,
        charge_notes=charge_notes,
        discount_auto_approve_threshold_pct=discount_auto_approve_threshold_pct,
        discount_supervisor_max_pct=discount_supervisor_max_pct,
        discount_disabled=discount_disabled,
        late_fee_waive_auto_approve_threshold_pct=late_fee_waive_auto_approve_threshold_pct,
        late_fee_waive_supervisor_max_pct=late_fee_waive_supervisor_max_pct,
        late_fee_waive_disabled=late_fee_waive_disabled,
    )
    db.add(p)
    db.flush()
    print(f"[created] Project: {name}  id={p.id}")
    return p


def _upsert_case(
    db,
    tenant: Tenant,
    owner: OwnerProfile,
    assigned_to: int,
    amount: Decimal,
    months: int,
    project_id: int | None = None,
    arrears_reason: str | None = None,
) -> None:
    # v1.6 — 推算账单期间 + 本金 + 滞纳金（基于月度欠费等额分摊）
    today = date.today()
    bill_end = date(today.year, today.month, 1) - timedelta(days=1)
    # 起始 = 终止往前推 months 个月的 1 号
    start_year = bill_end.year
    start_month = bill_end.month - months + 1
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    bill_start = date(start_year, start_month, 1)
    # 滞纳金按 5% 估算（演示用），principal = amount - late_fee
    late_fee = (amount * Decimal("0.05")).quantize(Decimal("0.01"))
    principal = (amount - late_fee).quantize(Decimal("0.01"))

    existing = db.execute(
        select(CollectionCase).where(
            CollectionCase.tenant_id == tenant.id,
            CollectionCase.owner_id == owner.id,
        )
    ).scalar_one_or_none()
    if existing:
        # 回填 project_id 到已存在的 case（demo 数据迁移）
        if existing.project_id is None and project_id is not None:
            existing.project_id = project_id
        # v1.6 — 回填账单字段
        if existing.bill_period_start is None:
            existing.bill_period_start = bill_start
        if existing.bill_period_end is None:
            existing.bill_period_end = bill_end
        if existing.principal_amount is None:
            existing.principal_amount = principal
        if existing.late_fee_amount is None:
            existing.late_fee_amount = late_fee
        if existing.arrears_reason is None and arrears_reason:
            existing.arrears_reason = arrears_reason
        print(f"[backfill] case_id={existing.id} bill_period={bill_start}~{bill_end}")
        return
    case = CollectionCase(
        tenant_id=tenant.id,
        owner_id=owner.id,
        project_id=project_id,
        assigned_to=assigned_to,
        pool_type="public",
        stage="new",
        amount_owed=amount,
        months_overdue=months,
        priority_score=months * 100,
        status="active",
        bill_period_start=bill_start,
        bill_period_end=bill_end,
        principal_amount=principal,
        late_fee_amount=late_fee,
        arrears_reason=arrears_reason,
    )
    db.add(case)
    db.flush()
    print(f"[created] CollectionCase: owner={owner.name}  amount={amount}  id={case.id}")


def _upsert_risk_keyword(db, tenant: Tenant | None, keyword: str, level: str, speaker: str, category: str) -> None:
    # tenant_id=None means platform-level keyword
    tid = tenant.id if tenant else None
    existing = db.execute(
        select(RiskKeyword).where(
            RiskKeyword.tenant_id == tid,
            RiskKeyword.keyword == keyword,
            RiskKeyword.category == category,
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  RiskKeyword: {keyword}")
        return
    kw = RiskKeyword(
        tenant_id=tid,
        category=category,
        speaker=speaker,
        level=level,
        keyword=keyword,
        is_active=True,
    )
    db.add(kw)
    db.flush()
    print(f"[created] RiskKeyword: {keyword}  level={level}  id={kw.id}")


def _upsert_law_firm(db) -> LawFirm:
    """v1.6 — 律所池 demo 数据。"""
    existing = db.execute(
        select(LawFirm).where(LawFirm.license_no == "FIRM_DEMO_001")
    ).scalar_one_or_none()
    if existing:
        print("[exists] LawFirm: 京诚律师事务所")
        return existing
    firm = LawFirm(
        name="京诚律师事务所",
        license_no="FIRM_DEMO_001",
        region="上海市",
        contact_name="张主任",
        contact_phone="02112345678",
        specialties=["物业纠纷", "调解", "小额诉讼"],
        enabled=True,
        accepting_orders=True,
        rating_avg=Decimal("4.80"),
        completed_orders=12,
    )
    db.add(firm)
    db.flush()
    print(f"[created] LawFirm: 京诚律师事务所  id={firm.id}")
    return firm


def _upsert_lawyer(db, firm: LawFirm, name: str, license_no: str, specialties: list[str]) -> LawFirmLawyer:
    existing = db.execute(
        select(LawFirmLawyer)
        .where(LawFirmLawyer.law_firm_id == firm.id)
        .where(LawFirmLawyer.name == name)
    ).scalar_one_or_none()
    if existing:
        print(f"[exists] Lawyer: {name}")
        return existing
    lawyer = LawFirmLawyer(
        law_firm_id=firm.id,
        name=name,
        license_no=license_no,
        specialties=specialties,
        is_active=True,
    )
    db.add(lawyer)
    db.flush()
    print(f"[created] Lawyer: {name}  id={lawyer.id}")
    return lawyer


def _upsert_law_firm_membership(
    db, user: UserAccount, firm: LawFirm, role_in_firm: str, lawyer: LawFirmLawyer | None = None
) -> LawFirmMembership:
    existing = db.execute(
        select(LawFirmMembership)
        .where(LawFirmMembership.user_id == user.id)
        .where(LawFirmMembership.law_firm_id == firm.id)
    ).scalar_one_or_none()
    if existing:
        if existing.role_in_firm != role_in_firm or existing.lawyer_id != (lawyer.id if lawyer else None):
            existing.role_in_firm = role_in_firm
            existing.lawyer_id = lawyer.id if lawyer else None
            db.flush()
            print(f"[update] LawFirmMembership: user={user.name}, role_in_firm={role_in_firm}")
        else:
            print(f"[exists] LawFirmMembership: user={user.name}, role_in_firm={role_in_firm}")
        return existing
    m = LawFirmMembership(
        user_id=user.id,
        law_firm_id=firm.id,
        lawyer_id=lawyer.id if lawyer else None,
        role_in_firm=role_in_firm,
        is_active=True,
    )
    db.add(m)
    db.flush()
    print(f"[created] LawFirmMembership: user={user.name}, role_in_firm={role_in_firm}")
    return m


def _upsert_legal_package(db, slug: str, package_type: str, name: str, price: Decimal) -> LegalServicePackage:
    existing = db.execute(
        select(LegalServicePackage)
        .where(LegalServicePackage.tenant_id.is_(None))
        .where(LegalServicePackage.slug == slug)
    ).scalar_one_or_none()
    if existing:
        return existing
    pkg = LegalServicePackage(
        tenant_id=None,
        slug=slug,
        package_type=package_type,
        name=name,
        price=price,
        platform_fee_rate=Decimal("0.25"),
        enabled=True,
        sort_order=0,
    )
    db.add(pkg)
    db.flush()
    print(f"[created] LegalServicePackage: {name}")
    return pkg


def _upsert_legal_order(
    db, tenant: Tenant, case: CollectionCase, package: LegalServicePackage,
    creator: UserAccount, status: str,
    firm: LawFirm | None = None, lawyer: LawFirmLawyer | None = None, notes: str = "",
) -> LegalConversionOrder | None:
    existing = db.execute(
        select(LegalConversionOrder)
        .where(LegalConversionOrder.tenant_id == tenant.id)
        .where(LegalConversionOrder.case_id == case.id)
        .where(LegalConversionOrder.package_id == package.id)
    ).scalar_one_or_none()
    if existing:
        return existing
    fee = (package.price * package.platform_fee_rate).quantize(Decimal("0.01"))
    now = datetime.now(timezone.utc)
    order = LegalConversionOrder(
        tenant_id=tenant.id,
        case_id=case.id,
        package_id=package.id,
        status=status,
        price_quoted=package.price,
        platform_fee_amount=fee,
        law_firm_id=firm.id if firm else None,
        lawyer_id=lawyer.id if lawyer else None,
        assigned_law_firm=firm.name if firm else None,
        assigned_lawyer_name=lawyer.name if lawyer else None,
        timeline_summary={"text": "demo seed — 见 v1.6"} if notes else None,
        notes=notes or None,
        created_by=creator.id,
        dispatched_at=now if status in {"dispatched", "in_service", "completed"} else None,
        completed_at=now if status == "completed" else None,
    )
    db.add(order)
    db.flush()
    print(f"[created] LegalConversionOrder: case={case.id} status={status}")
    return order


def _upsert_discount_offer(
    db, tenant: Tenant, case: CollectionCase, applicant: UserAccount,
    offer_type: str, applicant_role: str, original: Decimal, proposed: Decimal,
    status: str, reason: str, approver_role: str, installment_months: int | None = None,
    approver: UserAccount | None = None,
) -> None:
    existing = db.execute(
        select(DiscountOffer)
        .where(DiscountOffer.tenant_id == tenant.id)
        .where(DiscountOffer.case_id == case.id)
        .where(DiscountOffer.offer_type == offer_type)
    ).scalar_one_or_none()
    if existing:
        return
    pct = 0
    if original > 0:
        pct = int(((original - proposed) / original * Decimal(100)).quantize(Decimal("1")))
    pct = max(0, min(100, pct))
    now = datetime.now(timezone.utc)
    audit = [
        {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "actor": applicant.name,
            "action": f"发起减免申请（{pct}%）",
        }
    ]
    if status == "approved" and approver:
        audit.append({
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "actor": approver.name,
            "action": "批准（demo seed）",
        })
    offer = DiscountOffer(
        tenant_id=tenant.id,
        case_id=case.id,
        applicant_user_id=applicant.id,
        applicant_role=applicant_role,
        offer_type=offer_type,
        original_amount=original,
        proposed_amount=proposed,
        discount_pct=pct,
        installment_months=installment_months,
        reason=reason,
        status=status,
        approver_role_required=approver_role,
        approved_by_user_id=approver.id if (approver and status == "approved") else None,
        approved_at=now if status == "approved" else None,
        expires_at=now + timedelta(days=7),
        audit_trail=audit,
    )
    db.add(offer)
    db.flush()
    print(f"[created] DiscountOffer: case={case.id} status={status} pct={pct}%")


def _upsert_tenant_settings(db, tenant: Tenant) -> None:
    """v1.6 — 确保 TenantSettings 存在，使 admin 设置页和减免审批策略可用。"""
    existing = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if existing:
        return
    settings = TenantSettings(
        tenant_id=tenant.id,
        # defaults of all other columns auto-applied
    )
    db.add(settings)
    db.flush()
    print(f"[created] TenantSettings: tenant={tenant.name}")


def _set_shift_lead(db, user: UserAccount) -> None:
    """v1.6 — 标记督导为排班负责人。"""
    prefs = dict(user.preferences or {})
    if prefs.get("is_shift_lead") is True:
        return
    prefs["is_shift_lead"] = True
    user.preferences = prefs
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "preferences")
    print(f"[update] is_shift_lead=true for user {user.name}")


def _upsert_script_template(db, trigger_intent: str, title: str, content: str) -> None:
    existing = db.execute(
        select(ScriptTemplate).where(
            ScriptTemplate.trigger_intent == trigger_intent,
            ScriptTemplate.tenant_id.is_(None),
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  ScriptTemplate: {title}")
        return
    tpl = ScriptTemplate(
        tenant_id=None,
        title=title,
        trigger_intent=trigger_intent,
        content=content,
        version=1,
        is_active=True,
        usage_count=0,
    )
    db.add(tpl)
    db.flush()
    print(f"[created] ScriptTemplate: {title}  id={tpl.id}")


def main() -> None:
    print("=" * 60)
    print("seed_demo.py — 开始写入 Demo 数据")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1. 租户
        tenant = _upsert_tenant(db)

        # 2. 用户
        # 平台级用户（无 tenant membership）
        super_user, _ = _upsert_user(db, "13000000000", "平台超管")
        ops_user, _ = _upsert_user(db, "13000000001", "运营员")

        # 租户用户
        admin_user, _ = _upsert_user(db, "13000000002", "物业管理员")
        supervisor_user, _ = _upsert_user(db, "13000000003", "督导小李")
        agent_internal_user, _ = _upsert_user(db, "13000000004", "内勤小张")
        agent_external_user, _ = _upsert_user(db, "13000000005", "外勤小王")

        # 批 3 新增 5 个角色用户
        legal_user, _ = _upsert_user(db, "13000000006", "法务老周")
        workorder_user, _ = _upsert_user(db, "13000000007", "协调员小赵")
        pm_property_user, _ = _upsert_user(db, "13000000008", "项目经理（物业）")
        pm_provider_user, _ = _upsert_user(db, "13000000009", "项目经理（服务商）")
        provider_admin_user, _ = _upsert_user(db, "13000000010", "服务商管理员")

        # 3. Memberships
        # platform_super: no tenant membership (auth.py defaults to platform_superadmin)
        # platform_ops: needs membership to get role=platform_ops from login
        _upsert_membership(db, ops_user, tenant, "platform_ops")
        _upsert_membership(db, admin_user, tenant, "admin")
        _upsert_membership(db, supervisor_user, tenant, "supervisor")
        # v1.6.10 — 督导小李同时拥有催收员身份（多角色切换演示）
        _upsert_membership(db, supervisor_user, tenant, "agent_internal")
        _upsert_membership(db, agent_internal_user, tenant, "agent_internal")
        _upsert_membership(db, agent_external_user, tenant, "agent_external")
        _upsert_membership(db, legal_user, tenant, "legal")
        _upsert_membership(db, workorder_user, tenant, "coordinator")
        _upsert_membership(db, pm_property_user, tenant, "project_manager_property")

        # 3b. ServiceProvider + Contract (for provider_admin & pm_provider)
        provider = _upsert_provider(db)
        contract = _upsert_provider_contract(db, tenant, provider)
        _upsert_settlement(db, contract)
        _upsert_membership(
            db, pm_provider_user, tenant, "project_manager_provider", provider_id=provider.id
        )
        _upsert_membership(
            db, provider_admin_user, tenant, "provider_admin", provider_id=provider.id
        )

        # 3c. 项目（v1.4 — Project 成为一等公民；v1.6 加合同 + v1.6.1 减免覆盖演示）
        project_main = _upsert_project(
            db, tenant,
            name="金桂园 2026 年欠费催收",
            property_pm_user_id=pm_property_user.id,
            provider_id=provider.id,
            provider_pm_user_id=pm_provider_user.id,
            description="2026 年第一季度物业费欠费回收专项",
            charge_rate_per_sqm=Decimal("1.5"),
            charge_rate_text="住宅 1.5 元/㎡/月\n商铺 3.0 元/㎡/月\n车位 80 元/位/月",
            charge_period="monthly",
            contract_type="elected",
            contract_start_date=date(2024, 1, 1),
            contract_end_date=date(2026, 12, 31),
            charge_notes="逾期按日加收 0.5‰ 滞纳金。",
            # 沿用租户默认（10/30/启用）— 滞纳金减免也走默认（50/100/启用）
        )
        project_elevator = _upsert_project(
            db, tenant,
            name="翠湖湾电梯专项整改",
            property_pm_user_id=pm_property_user.id,
            description="电梯维护基金筹集（业委会自营，无服务商）",
            charge_rate_per_sqm=Decimal("0.8"),
            charge_rate_text="按建筑面积 0.8 元/㎡/年（一次性年缴）",
            charge_period="annual",
            contract_type="interim_management",
            contract_start_date=date(2025, 6, 1),
            contract_end_date=date(2027, 5, 31),
            charge_notes="电梯专项基金；不允许本金打折，但允许滞纳金减免。",
            # v1.6.1 — 项目级覆盖：业委会专项基金不允许「本金打折」
            discount_disabled=True,
            # v1.6.2 — 但仍允许「滞纳金减免」（独立策略，沿用租户默认）
        )
        project_commercial = _upsert_project(
            db, tenant,
            name="紫荆商业广场 2026 商铺欠费",
            property_pm_user_id=pm_property_user.id,
            description="商铺业主欠费多元化处理（弹性减免空间大）",
            charge_rate_per_sqm=Decimal("3.0"),
            charge_rate_text="商铺 3.0 元/㎡/月\n超大商铺 (>500㎡) 2.5 元/㎡/月",
            charge_period="monthly",
            contract_type="elected",
            contract_start_date=date(2023, 7, 1),
            contract_end_date=date(2028, 6, 30),
            charge_notes="商业空置率高，弹性减免空间大。",
            # v1.6.1 — 商业项目放宽「本金打折」阈值
            discount_auto_approve_threshold_pct=30,
            discount_supervisor_max_pct=50,
            discount_disabled=False,
            # v1.6.2 — 滞纳金可全免（鼓励本金回收）
            late_fee_waive_auto_approve_threshold_pct=100,
            late_fee_waive_supervisor_max_pct=100,
            late_fee_waive_disabled=False,
        )

        # 4. OwnerProfile × 7（金桂园 3 + 翠湖湾 2 + 商业广场 2）
        owners_data = [
            ("张大明", "13100000001", "1栋", "101", Decimal("3200.00"), 3, project_main.id, "经济困难"),
            ("李小红", "13100000002", "2栋", "202", Decimal("5600.00"), 6, project_main.id, "服务质量异议"),
            ("王建国", "13100000003", "3栋", "303", Decimal("1800.00"), 2, project_main.id, "其他"),
            ("陈美华", "13100000004", "1栋", "405", Decimal("9100.00"), 9, project_elevator.id, "经济困难"),
            ("刘志强", "13100000005", "4栋", "501", Decimal("2400.00"), 4, project_elevator.id, "房屋空置"),
            ("赵铭海", "13100000006", "A座", "1101", Decimal("18000.00"), 6, project_commercial.id, "房屋空置"),
            ("孙菁菁", "13100000007", "B座", "302", Decimal("6800.00"), 4, project_commercial.id, "服务质量异议"),
        ]
        for name, phone, building, room, amount, months, pid, reason in owners_data:
            owner = _upsert_owner(db, tenant, name, phone, building, room)
            _upsert_case(db, tenant, owner, agent_internal_user.id, amount, months,
                         project_id=pid, arrears_reason=reason)

        # v1.6.10 — 给督导小李（同时是催收员）单独分配 2 个案件（多角色切换演示）
        supervisor_owners = [
            ("陈小燕", "13100000008", "2栋", "0601", Decimal("21000.00"), 17, project_elevator.id, "服务质量异议（长期欠费）"),
            ("林瀚", "13100000009", "1栋", "0203", Decimal("4500.00"), 5, project_main.id, "其他"),
        ]
        for name, phone, building, room, amount, months, pid, reason in supervisor_owners:
            owner = _upsert_owner(db, tenant, name, phone, building, room)
            _upsert_case(db, tenant, owner, supervisor_user.id, amount, months,
                         project_id=pid, arrears_reason=reason)

        # 5. RiskKeyword
        _upsert_risk_keyword(
            db,
            tenant=None,  # platform-level preset
            keyword="投诉",
            level="L1",
            speaker="owner",
            category="complaint",
        )

        # 6. ScriptTemplate
        _upsert_script_template(
            db,
            trigger_intent="经济困难",
            title="共情还款建议",
            content="您说的我理解，经济压力确实不小。我们可以根据您的实际情况协商一个分期还款方案，您觉得每月还多少比较合适？",
        )

        # 7. v1.6 — TenantSettings (减免阈值默认 10/30, 启用)
        _upsert_tenant_settings(db, tenant)

        # 8. v1.6 — 督导小李设置为排班负责人
        _set_shift_lead(db, supervisor_user)

        # 9. v1.6 — LawFirm + 3 律师 + 多 membership 给 13000000006
        firm = _upsert_law_firm(db)
        lawyer_li = _upsert_lawyer(db, firm, "李律师", "LIC0011", ["物业纠纷", "调解"])
        lawyer_chen = _upsert_lawyer(db, firm, "陈律师", "LIC0012", ["小额诉讼"])
        _upsert_lawyer(db, firm, "周律师", "LIC0013", ["律师函", "催收"])
        # legal_user 同时挂为律所代表 + 兼任「李律师」（演示多 membership）
        _upsert_law_firm_membership(db, legal_user, firm, "admin")
        _upsert_law_firm_membership(db, legal_user, firm, "lawyer", lawyer=lawyer_li)

        # 10. v1.6 — Legal service packages
        pkg_letter = _upsert_legal_package(db, "lawyer-letter-std", "lawyer_letter", "律师函（标准）", Decimal("800.00"))
        pkg_mediate = _upsert_legal_package(db, "mediation-std", "mediation", "诉前调解", Decimal("1800.00"))
        pkg_small = _upsert_legal_package(db, "small-claims-std", "small_claims", "小额诉讼", Decimal("3200.00"))
        pkg_full = _upsert_legal_package(db, "full-agency-std", "full_agency", "完整代理", Decimal("4800.00"))

        # 11. v1.6 — Demo legal orders 跨 4 个状态
        all_cases = db.execute(
            select(CollectionCase).where(CollectionCase.tenant_id == tenant.id).order_by(CollectionCase.id)
        ).scalars().all()
        if len(all_cases) >= 4:
            _upsert_legal_order(db, tenant, all_cases[0], pkg_letter, supervisor_user, "pending",
                                notes="业主拒接电话，建议先发律师函")
            _upsert_legal_order(db, tenant, all_cases[1], pkg_mediate, supervisor_user, "dispatched",
                                firm=firm, notes="服务质量异议，先调解")
            _upsert_legal_order(db, tenant, all_cases[2], pkg_full, supervisor_user, "in_service",
                                firm=firm, lawyer=lawyer_li, notes="恶意拖欠，全代理")
            _upsert_legal_order(db, tenant, all_cases[3], pkg_small, supervisor_user, "completed",
                                firm=firm, lawyer=lawyer_chen, notes="立案后业主主动缴清，撤诉")

        # 12. v1.6 — Demo discount offers 跨多个状态
        if len(all_cases) >= 3:
            _upsert_discount_offer(
                db, tenant, all_cases[0], agent_internal_user,
                offer_type="principal_discount", applicant_role="agent",
                original=all_cases[0].amount_owed or Decimal("3200"),
                proposed=(all_cases[0].amount_owed or Decimal("3200")) * Decimal("0.80"),
                status="pending_supervisor", approver_role="supervisor",
                reason="业主家庭遭遇变故（配偶失业），愿一次性缴 80%。",
            )
            _upsert_discount_offer(
                db, tenant, all_cases[1], agent_internal_user,
                offer_type="principal_discount", applicant_role="agent",
                original=all_cases[1].amount_owed or Decimal("5600"),
                proposed=(all_cases[1].amount_owed or Decimal("5600")) * Decimal("0.50"),
                status="pending_admin", approver_role="admin",
                reason="业主主张电梯故障 3 次的服务质量问题，要求减免 50%。需 admin 审批。",
            )
            _upsert_discount_offer(
                db, tenant, all_cases[2], agent_internal_user,
                offer_type="installment", applicant_role="agent",
                original=all_cases[2].amount_owed or Decimal("1800"),
                proposed=all_cases[2].amount_owed or Decimal("1800"),
                status="approved", approver_role="supervisor",
                installment_months=6, approver=supervisor_user,
                reason="业主收入不稳定但愿意还款，申请 6 期分期。无折扣。",
            )

        db.commit()
        print("=" * 60)
        print("seed_demo.py — 全部写入完成 ✅")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
