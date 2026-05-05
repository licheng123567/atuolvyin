"""seed_demo.py — 幂等 Demo 数据 seed 脚本.

用法:
    docker exec autoluyin-backend python -m scripts.seed_demo

重复运行安全（已存在则跳过）。
"""
from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import select

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.models.case import CollectionCase, OwnerProfile
from app.models.risk import RiskKeyword
from app.models.script import ScriptTemplate
from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount

DEMO_PASSWORD = "Demo@123!"


def _upsert_tenant(db) -> Tenant:
    existing = db.execute(
        select(Tenant).where(Tenant.credit_code == "DEMO000000000001")
    ).scalar_one_or_none()
    if existing:
        print("[exists] Tenant: Demo 物业")
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


def _upsert_membership(db, user: UserAccount, tenant: Tenant, role: str) -> None:
    existing = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant.id,
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
        is_active=True,
    )
    db.add(membership)
    db.flush()
    print(f"[created] Membership: {user.name} -> {role}  tenant_id={tenant.id}")


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


def _upsert_case(
    db,
    tenant: Tenant,
    owner: OwnerProfile,
    assigned_to: int,
    amount: Decimal,
    months: int,
) -> None:
    existing = db.execute(
        select(CollectionCase).where(
            CollectionCase.tenant_id == tenant.id,
            CollectionCase.owner_id == owner.id,
        )
    ).scalar_one_or_none()
    if existing:
        print(f"[exists]  CollectionCase for owner_id={owner.id}")
        return
    case = CollectionCase(
        tenant_id=tenant.id,
        owner_id=owner.id,
        assigned_to=assigned_to,
        pool_type="public",
        stage="new",
        amount_owed=amount,
        months_overdue=months,
        priority_score=months * 100,
        status="active",
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

        # 3. Memberships
        # platform_super: no tenant membership (auth.py defaults to platform_superadmin)
        # platform_ops: needs membership to get role=platform_ops from login
        _upsert_membership(db, ops_user, tenant, "platform_ops")
        _upsert_membership(db, admin_user, tenant, "admin")
        _upsert_membership(db, supervisor_user, tenant, "supervisor")
        _upsert_membership(db, agent_internal_user, tenant, "agent_internal")
        _upsert_membership(db, agent_external_user, tenant, "agent_external")

        # 4. OwnerProfile × 5
        owners_data = [
            ("张大明", "13100000001", "1栋", "101", Decimal("3200.00"), 3),
            ("李小红", "13100000002", "2栋", "202", Decimal("5600.00"), 6),
            ("王建国", "13100000003", "3栋", "303", Decimal("1800.00"), 2),
            ("陈美华", "13100000004", "1栋", "405", Decimal("9100.00"), 9),
            ("刘志强", "13100000005", "4栋", "501", Decimal("2400.00"), 4),
        ]
        for name, phone, building, room, amount, months in owners_data:
            owner = _upsert_owner(db, tenant, name, phone, building, room)
            _upsert_case(db, tenant, owner, agent_internal_user.id, amount, months)

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
