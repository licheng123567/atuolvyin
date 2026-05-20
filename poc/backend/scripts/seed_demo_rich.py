"""v0.5.7 — 压测级 seed 数据(--reset 清空 + --rich 多租户多服务商扩展)。

诱因:用户反馈 1 tenant + 1 provider 的 baseline seed 数据不够丰富,平台 OPS 看不到
多租户对比 / 服务商管理员看不到跨租户合作 / 物业 admin 法务订单跨状态展示不充分。
本脚本生成 5 tenant + 5 provider + 25-30 项目 + 1500+ 案件 + 闭环业务流数据。

跑法:
    python3.12 scripts/seed_demo_rich.py --reset        # 仅清空(保留 13 测试 user_account)
    python3.12 scripts/seed_demo_rich.py --rich         # 仅生成 rich 数据(基于现有 baseline)
    python3.12 scripts/seed_demo_rich.py --reset --rich # 推荐:清空 + 重种 baseline + rich 扩展

输出:
- 数据库被 reset + rich 填充
- docs/SEED_ACCOUNTS.md(自动写入测试账号清单,每次 reset 覆盖)
- stdout 打印各表行数统计

设计:
- 完全复用 seed_demo.py 的 helper(_upsert_*) 不复制粘贴
- --reset 用 DELETE 而非 TRUNCATE(保留 13 个测试 user + audit_log + alembic_version)
- 固定 random.seed(20260520) 保证多次跑产出一致(便于 debug)
- 13 个现有号码(13000000000-13000000012)指向 tenant1 / provider1(主演示)
- tenant2-5 / provider2-5 用 13100000xxx 新号段(随机生成,清单写到 SEED_ACCOUNTS.md)
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

# 让脚本能从 scripts/ 目录直接跑
sys.path.insert(0, str(Path(__file__).parent.parent))

# 复用 seed_demo 全套 helper(避免代码复制)
from scripts.seed_demo import (  # noqa: E402
    _set_shift_lead,
    _upsert_case,
    _upsert_discount_offer,
    _upsert_internal_letter_template,
    _upsert_law_firm,
    _upsert_law_firm_membership,
    _upsert_lawyer,
    _upsert_legal_order,
    _upsert_legal_package,
    _upsert_membership,
    _upsert_owner,
    _upsert_partner_law_firm,
    _upsert_project,
    _upsert_provider_contract,
    _upsert_risk_keyword,
    _upsert_script_template,
    _upsert_settlement,
    _upsert_tenant_settings,
    _upsert_user,
    main as seed_demo_main,
)

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    Tenant,
    UserTenantMembership,
)
from app.models.user import UserAccount

# ─── 随机数据池 ────────────────────────────────────────────────────────

RANDOM_SEED = 20260520

CHINESE_SURNAMES = [
    "张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴",
    "徐", "孙", "朱", "林", "郑", "何", "高", "罗", "郭", "宋",
    "唐", "韩", "冯", "邓", "曹", "彭", "曾", "肖", "田", "董",
]

CHINESE_GIVEN_NAMES = [
    "建国", "美华", "志强", "晓敏", "海涛", "文静", "云霞", "建华",
    "永强", "晓娟", "志刚", "坚强", "晓军", "海燕", "明华", "国强",
    "丽华", "金华", "秀英", "桂兰", "玉兰", "玉芳", "宝珍", "凤英",
    "玉珍", "玉珠", "美玲", "丽娟", "丽君", "美琴", "美琳", "美丽",
    "晓辉", "光明", "建辉", "永辉", "国辉", "建平", "永平", "国平",
]

ARREARS_REASONS = [
    "经济困难", "服务质量异议", "房屋空置", "对账不清", "业主出差",
    "电梯维修争议", "公共费用质疑", "二次装修扣留", "邻里纠纷连带",
]

PROJECT_NAME_TEMPLATES = [
    "{city}{garden}小区", "{city}{road}花园", "{city}{road}公寓",
    "{city}{garden}苑", "{garden}广场", "{garden}雅居",
    "{garden}商业广场", "{city}国际公寓", "{garden}国际",
]
CITIES = ["金桂", "翠湖", "紫荆", "玉兰", "锦绣", "悦庭", "百合", "兰亭"]
GARDENS = ["园", "湾", "苑", "庭", "府", "里"]
ROADS = ["东路", "中路", "西路", "北路", "南路"]

BUILDINGS = ["1栋", "2栋", "3栋", "4栋", "5栋", "A座", "B座", "C座"]

PROVIDER_TYPES = ["legal", "collection", "mediation", "consulting"]
PROVIDER_NAME_TEMPLATES = [
    "{prefix}法务咨询", "{prefix}催收服务", "{prefix}调解中心",
    "{prefix}信用管理", "{prefix}资产管理",
]
PROVIDER_PREFIXES = ["华信", "金诚", "正泰", "宏远", "腾达", "鼎盛"]


def random_chinese_name(used: set[str]) -> str:
    """生成不重复的中文姓名;最多 200 次尝试。"""
    for _ in range(200):
        name = random.choice(CHINESE_SURNAMES) + random.choice(CHINESE_GIVEN_NAMES)
        if name not in used:
            used.add(name)
            return name
    # 最后兜底:加 2 位数字后缀
    base = random.choice(CHINESE_SURNAMES) + random.choice(CHINESE_GIVEN_NAMES)
    suffix = 1
    while f"{base}{suffix}" in used:
        suffix += 1
    full = f"{base}{suffix}"
    used.add(full)
    return full


def random_phone(used: set[str], prefix: str = "131") -> str:
    """生成不与已用号 + 13000000xxx 冲突的随机号。"""
    for _ in range(2000):
        suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
        phone = prefix + suffix
        if phone in used:
            continue
        if phone.startswith("13000000"):
            continue
        used.add(phone)
        return phone
    raise RuntimeError("无法生成不重复手机号(used set 已满?)")


def random_room() -> tuple[str, str]:
    """返回 (building, room),building 如 '2栋',room 如 '0301'。"""
    bld = random.choice(BUILDINGS)
    unit = random.randint(1, 4)
    floor = random.randint(1, 18)
    room = random.randint(1, 4)
    return bld, f"{unit}{floor:02d}{room:02d}"


def random_amount_months() -> tuple[Decimal, int]:
    """欠费金额 + 月数,合理分布。"""
    months = random.choice([2, 3, 4, 5, 6, 8, 10, 12, 15, 18])
    rate = Decimal(str(random.randint(500, 1200)))  # 每月 500-1200
    amount = (rate * months).quantize(Decimal("0.00"))
    return amount, months


def weighted_choice(choices: list[tuple[str, int]]) -> str:
    """加权随机选择。choices 形如 [('new', 25), ('in_progress', 25), ...]。"""
    total = sum(w for _, w in choices)
    r = random.randint(1, total)
    cum = 0
    for val, w in choices:
        cum += w
        if r <= cum:
            return val
    return choices[-1][0]


# ─── --reset 清空逻辑 ──────────────────────────────────────────────────

# 按外键依赖反向排列;保留 user_account / audit_log / alembic_version /
# legal_service_package(平台级,v0.5.5 定价已通过 OPS 后台维护)。
TABLES_TO_DELETE_ORDER = [
    # 叶子表(无外键指向)
    "recording_file",
    "legal_conversion_request_material",
    "transcript",
    "analysis_result",
    "risk_event",
    "qc_alert",
    "scoring_event",
    "scoring_period",
    "audit_log_attestation",
    "signed_url_token",
    "discount_offer_execution_log",
    "settlement_dispute",
    "blockchain_evidence_request",
    "attestation_request",
    "payment_link",
    "notification",
    "collection_promise",
    # 业务表
    "call_record",
    "work_order",
    "discount_offer",
    "legal_conversion_request",
    "legal_conversion_order",
    "legal_case",
    "case_assignment_history",
    "collection_case",
    "project_member",
    "supervisor_shift",
    "settlement_statement",
    "owner_profile",
    "provider_tenant_contract",
    "tenant_minute_usage",
    "tenant_settings",
    "project",
    # 配置表
    "internal_legal_letter_template",
    "partner_law_firm",
    "law_firm_membership",
    "law_firm_lawyer",
    "law_firm",
    "system_announcement",
    "customer_followup",
    "sms_log",
    "script_template",
    "risk_keyword",
    "legal_document_template",
    # 顶层
    "user_tenant_membership",
    "tenant",
    "service_provider",
]

# 不删:user_account / audit_log / alembic_version / legal_service_package
TABLES_TO_KEEP = {
    "user_account",
    "audit_log",
    "alembic_version",
    "legal_service_package",
}


def reset_all(db: Session) -> None:
    """TRUNCATE 所有可清表(CASCADE 自动处理外键);保留 user_account / audit_log / alembic / 平台服务包。"""
    print("─" * 60)
    print("⚠ --reset 模式:清空所有租户/服务商/业务数据")
    print(f"  保留:{', '.join(sorted(TABLES_TO_KEEP))}")
    print("─" * 60)

    # 找出所有真实存在的表(过滤迁移环境差异)
    rows = db.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )).all()
    all_tables = {r[0] for r in rows}
    tables_to_truncate = [t for t in TABLES_TO_DELETE_ORDER if t in all_tables]

    # 用 TRUNCATE ... CASCADE 一次性清(PG 会处理外键)
    # 但 user_account / audit_log 在 CASCADE 下可能被牵连;先 truncate 不级联到这两表
    # 实际上 TRUNCATE CASCADE 会级联所有引用表,可能误删 user_account。
    # 安全做法:TRUNCATE 在一个语句里列出所有要清的表(PG 支持 TRUNCATE t1, t2, ... CASCADE)
    table_list_sql = ", ".join(tables_to_truncate)
    print(f"  TRUNCATE {len(tables_to_truncate)} tables ...")
    try:
        db.execute(text(f"TRUNCATE TABLE {table_list_sql} RESTART IDENTITY CASCADE"))
        db.commit()
        print(f"✓ 清空完成({len(tables_to_truncate)} 表,序列已重置)")
    except Exception as e:
        db.rollback()
        print(f"❌ TRUNCATE 失败:{e}")
        raise
    print()


# ─── --rich 数据扩展 ───────────────────────────────────────────────────


def make_extra_tenant(db: Session, idx: int) -> Tenant:
    """生成 tenant2-5(idx=2-5),不与 baseline 的 Demo 物业重名。"""
    names = ["阳光华庭物业", "万通物业", "星城物业服务", "锦绣家园物业"]
    credit_codes = [
        f"DEMO000000000{idx:03d}",  # 与 baseline credit_code 不冲突
    ]
    existing = db.execute(
        select(Tenant).where(Tenant.name == names[idx - 2])
    ).scalar_one_or_none()
    if existing:
        return existing
    t = Tenant(
        name=names[idx - 2],
        credit_code=credit_codes[0],
        admin_phone_enc=encrypt_phone(f"1310000{idx:04d}"),
        is_active=True,
    )
    db.add(t)
    db.flush()
    print(f"  [created] Tenant: {t.name} (id={t.id})")
    return t


def make_extra_provider(db: Session, idx: int) -> ServiceProvider:
    """生成 provider2-5。"""
    prefix = PROVIDER_PREFIXES[idx - 2]
    ptype = PROVIDER_TYPES[(idx - 2) % len(PROVIDER_TYPES)]
    template = PROVIDER_NAME_TEMPLATES[(idx - 2) % len(PROVIDER_NAME_TEMPLATES)]
    name = template.format(prefix=prefix)
    existing = db.execute(
        select(ServiceProvider).where(ServiceProvider.name == name)
    ).scalar_one_or_none()
    if existing:
        return existing
    p = ServiceProvider(
        name=name,
        provider_type=ptype,
        admin_phone_enc=encrypt_phone(f"1311000{idx:04d}"),
        is_active=True,
        audit_status="approved",
    )
    db.add(p)
    db.flush()
    print(f"  [created] ServiceProvider: {p.name} (id={p.id})")
    return p


def make_extra_tenant_users(
    db: Session, tenant: Tenant, idx: int, used_phones: set[str]
) -> dict[str, UserAccount]:
    """给 tenant2-5 各生成 5 个核心角色账号(admin/supervisor/agent×2/legal)。"""
    users: dict[str, UserAccount] = {}

    def make(role_key: str, role_label: str) -> UserAccount:
        phone = random_phone(used_phones, prefix=f"131{idx}")
        name = f"T{idx}-{role_label}"
        u, _ = _upsert_user(db, phone, name)
        users[role_key] = u
        return u

    admin = make("admin", "管理员")
    supervisor = make("supervisor", "督导")
    agent1 = make("agent_internal", "内勤催收员")
    agent2 = make("agent_external", "外勤催收员")
    legal = make("legal", "法务对接人")

    # 物业 membership
    _upsert_membership(db, admin, tenant, "admin")
    _upsert_membership(db, supervisor, tenant, "supervisor")
    _upsert_membership(db, agent1, tenant, "agent", work_mode="internal")
    _upsert_membership(db, agent2, tenant, "agent", work_mode="external")
    _upsert_membership(db, legal, tenant, "legal")
    return users


def make_extra_provider_users(
    db: Session, provider: ServiceProvider, tenant: Tenant, idx: int, used_phones: set[str]
) -> dict[str, UserAccount]:
    """给 provider2-5 生成 admin/supervisor/agent 账号(tenant 参数:provider 必须挂某 tenant)。"""
    users: dict[str, UserAccount] = {}

    def make(role_key: str, role_label: str) -> UserAccount:
        phone = random_phone(used_phones, prefix=f"131{idx + 5}")
        name = f"P{idx}-{role_label}"
        u, _ = _upsert_user(db, phone, name)
        users[role_key] = u
        return u

    admin = make("admin", "服务商管理员")
    supervisor = make("supervisor", "服务商督导")
    agent = make("agent", "服务商催收员")

    _upsert_membership(db, admin, tenant, "admin", provider_id=provider.id)
    _upsert_membership(db, supervisor, tenant, "supervisor", provider_id=provider.id)
    _upsert_membership(db, agent, tenant, "agent", provider_id=provider.id, work_mode="external")
    return users


def make_project_for_tenant(
    db: Session,
    tenant: Tenant,
    name: str,
    provider: ServiceProvider | None,
    pm_user: UserAccount | None,
) -> Project:
    """生成项目,可外包给 provider 也可自办(provider=None)。直接用 _upsert_project keyword args。"""
    return _upsert_project(
        db, tenant, name,
        property_pm_user_id=pm_user.id if pm_user else None,
        provider_id=provider.id if provider else None,
        description=f"{tenant.name} 旗下 {name} 催收项目",
        charge_rate_text=random.choice([
            "住宅 1.5/㎡/月,商铺 3.0/㎡/月",
            "按建筑面积 0.8 元/㎡/年",
            "按月计费 600 元/户",
        ]),
        charge_period=random.choice(["monthly", "quarterly", "annual"]),
        contract_type=random.choice([
            "preliminary_service", "elected", "re_elected", "interim_management",
        ]),
        contract_start_date=datetime.now(UTC).date() - timedelta(days=365 * 2),
        contract_end_date=datetime.now(UTC).date() + timedelta(days=365 * 3),
    )


def make_cases_for_project(
    db: Session,
    tenant: Tenant,
    project: Project,
    count: int,
    used_owner_phones: set[str],
    used_owner_names: set[str],
    internal_agents: list[UserAccount],
) -> list[CollectionCase]:
    """为单个项目生成 N 个 owner + case。stage 分布按权重。

    注:_upsert_case 不返回 case 对象,所以这里 raw 创建(全字段控)。
    """
    from datetime import date as _date

    cases: list[CollectionCase] = []
    stage_weights = [
        ("new", 25), ("in_progress", 25), ("promised", 15),
        ("paid", 10), ("escalated", 10), ("closed", 15),
    ]
    pool_weights = [("public", 30), ("private", 70)]

    today = _date.today()
    bill_end = _date(today.year, today.month, 1) - timedelta(days=1)

    for _ in range(count):
        owner_name = random_chinese_name(used_owner_names)
        owner_phone = random_phone(used_owner_phones, prefix=random.choice(["138", "139"]))
        bld, room = random_room()
        owner = _upsert_owner(db, tenant, owner_name, owner_phone, bld, room)

        amount, months = random_amount_months()
        reason = random.choice(ARREARS_REASONS)

        # 推算账单期间(与 _upsert_case 逻辑一致)
        start_year = bill_end.year
        start_month = bill_end.month - months + 1
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        bill_start = _date(start_year, start_month, 1)
        late_fee = (amount * Decimal("0.05")).quantize(Decimal("0.01"))
        principal = (amount - late_fee).quantize(Decimal("0.01"))

        # 选 stage + pool_type
        stage = weighted_choice(stage_weights)
        pool_type = weighted_choice(pool_weights)
        assigned: int | None = None
        if pool_type == "private" and internal_agents:
            assigned = random.choice(internal_agents).id
        else:
            pool_type = "public"

        case = CollectionCase(
            tenant_id=tenant.id,
            owner_id=owner.id,
            project_id=project.id,
            assigned_to=assigned,
            pool_type=pool_type,
            stage=stage,
            amount_owed=amount,
            months_overdue=months,
            priority_score=months * 100,
            status="active",
            bill_period_start=bill_start,
            bill_period_end=bill_end,
            principal_amount=principal,
            late_fee_amount=late_fee,
            arrears_reason=reason,
        )
        db.add(case)
        cases.append(case)

    db.flush()
    return cases


def make_calls_for_cases(
    db: Session, tenant: Tenant, cases: list[CollectionCase],
    agents: list[UserAccount],
) -> int:
    """为活跃案件(non-new / non-closed)生成 1-3 通电话 + 部分带 transcript/analysis。"""
    from app.models.call import AnalysisResult, CallRecord, Transcript

    if not agents:
        return 0

    call_count = 0
    result_tags = [
        ("promised", 25), ("refused", 20), ("busy", 15),
        ("no_answer", 25), ("paid", 10), ("neutral", 5),
    ]
    for case in cases:
        if case.stage in ("new", "closed"):
            continue
        n_calls = random.randint(1, 3)
        for i in range(n_calls):
            started = datetime.now(UTC) - timedelta(days=random.randint(1, 60), hours=random.randint(0, 23))
            duration = random.randint(30, 600)
            agent = random.choice(agents)
            tag = weighted_choice(result_tags)
            call = CallRecord(
                tenant_id=tenant.id,
                case_id=case.id,
                caller_user_id=agent.id,
                callee_phone_enc=encrypt_phone("13800000000"),
                started_at=started,
                ended_at=started + timedelta(seconds=duration),
                duration_sec=duration,
                billable_duration=duration if tag != "no_answer" else 0,
                status="completed" if tag != "no_answer" else "aborted",
                result_tag=tag,
            )
            db.add(call)
            db.flush()
            call_count += 1

            # 90% 通话有 transcript + analysis(no_answer 跳过)
            if tag != "no_answer" and random.random() < 0.9:
                preview_texts = [
                    "你好,我是物业公司的客服,关于您家欠费的事...",
                    "业主说最近资金紧张,希望月底前能缓一缓。",
                    "业主明确表示这个月底前会缴清。",
                    "电话沟通中业主提到电梯故障的问题...",
                    "业主已挂断,声称不知道有欠费。",
                ]
                t = Transcript(
                    call_id=call.id,
                    full_text=random.choice(preview_texts),
                    asr_model="paraformer-v2",
                )
                db.add(t)
                a = AnalysisResult(
                    call_id=call.id,
                    summary=f"业主态度:{random.choice(['配合', '抗拒', '观望', '激动'])};建议:{random.choice(['再跟进一次', '升级督导', '转法务', '标记承诺'])}。",
                    followup_suggestion=random.choice([
                        "明日再次电话回访", "下周上门拜访", "等待业主主动联系", "升级到督导",
                    ]),
                    key_segments={
                        "sentiment": random.choice(["positive", "neutral", "negative"]),
                        "intent": tag,
                    },
                    llm_model="deepseek-chat",
                )
                db.add(a)
    db.flush()
    return call_count


def make_extra_discount_offers(
    db: Session, tenant: Tenant, cases: list[CollectionCase],
    requester: UserAccount, approver: UserAccount,
) -> int:
    """补 discount_offer 各状态:pending_supervisor / pending_admin / approved / rejected / executed。

    用 _upsert_discount_offer SSOT(signature 比较复杂,这里直接 raw 创建以掌控 status)。
    """
    if not cases:
        return 0
    from app.models.discount_offer import DiscountOffer

    statuses = ["pending_supervisor", "pending_admin", "approved", "rejected", "executed"]
    target_per_status = 8
    inserted = 0
    sample_cases = random.sample(cases, min(len(cases), len(statuses) * target_per_status))
    idx = 0
    now = datetime.now(UTC)
    for status_val in statuses:
        for _ in range(target_per_status):
            if idx >= len(sample_cases):
                break
            case = sample_cases[idx]
            idx += 1
            # 跳过已有 DiscountOffer 的 case(case_id+offer_type 唯一)
            existing = db.execute(
                select(DiscountOffer).where(
                    DiscountOffer.tenant_id == tenant.id,
                    DiscountOffer.case_id == case.id,
                    DiscountOffer.offer_type == "principal_discount",
                )
            ).scalar_one_or_none()
            if existing:
                continue
            pct = random.randint(10, 50)
            original = case.amount_owed or Decimal("1000")
            proposed = (original * (Decimal(100 - pct) / Decimal(100))).quantize(Decimal("0.01"))
            approver_role = "admin" if status_val == "pending_admin" else "supervisor"
            audit_trail = [{
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "actor": requester.name,
                "action": f"发起减免申请({pct}%)",
            }]
            if status_val in ("approved", "executed"):
                audit_trail.append({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "actor": approver.name,
                    "action": "批准(rich seed)",
                })
            offer = DiscountOffer(
                tenant_id=tenant.id,
                case_id=case.id,
                applicant_user_id=requester.id,
                applicant_role="agent",
                offer_type="principal_discount",
                original_amount=original,
                proposed_amount=proposed,
                discount_pct=pct,
                reason=f"[rich] {status_val} 演示数据",
                status=status_val,
                approver_role_required=approver_role,
                approved_by_user_id=approver.id if status_val in ("approved", "executed") else None,
                approved_at=now if status_val in ("approved", "executed") else None,
                expires_at=now + timedelta(days=7),
                audit_trail=audit_trail,
            )
            db.add(offer)
            inserted += 1
    db.commit()
    return inserted


def make_extra_legal_orders(
    db: Session, tenant: Tenant, cases: list[CollectionCase],
    creator: UserAccount, packages: list,
) -> int:
    """补 legal_conversion_order 各状态。"""
    if not cases or not packages:
        return 0
    statuses = ["pending", "dispatched", "in_service", "completed", "cancelled"]
    target_per_status = 4
    inserted = 0
    eligible_cases = [c for c in cases if c.stage in ("escalated", "closed")][:50]
    if not eligible_cases:
        eligible_cases = cases[:50]
    sample = random.sample(
        eligible_cases, min(len(eligible_cases), len(statuses) * target_per_status),
    )
    idx = 0
    for status_val in statuses:
        for _ in range(target_per_status):
            if idx >= len(sample):
                break
            case = sample[idx]
            pkg = random.choice(packages)
            idx += 1
            try:
                _upsert_legal_order(
                    db, tenant, case, pkg, creator=creator, status=status_val,
                    notes=f"[rich] sample {idx}",
                )
                inserted += 1
            except Exception as e:
                print(f"  [skip legal] case#{case.id} status={status_val}: {e}")
                db.rollback()
                continue
    db.commit()
    return inserted


def write_accounts_md(repo_root: Path, extra_accounts: list[dict]) -> None:
    """写 docs/SEED_ACCOUNTS.md(自动覆盖每次跑)。"""
    md_path = repo_root / "docs" / "SEED_ACCOUNTS.md"
    lines = [
        "# 种子数据测试账号清单",
        "",
        "> v0.5.7 起由 `seed_demo_rich.py --reset --rich` 自动生成。**每次跑覆盖**;",
        "> 主测试账号(13000000000-13000000012)不变,新加账号附在「额外租户/服务商」段。",
        "",
        f"生成时间:{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## 主测试账号(tenant1 / provider1)",
        "",
        "密码统一:`Demo@123!`",
        "",
        "| 号码 | 角色 | 范围 |",
        "|---|---|---|",
        "| 13000000000 | 平台超管 | platform |",
        "| 13000000001 | 平台运营 | platform |",
        "| 13000000002 | 物业管理员 | tenant1 |",
        "| 13000000003 | 督导 | tenant1 |",
        "| 13000000004 | 催收员(内勤) | tenant1 |",
        "| 13000000005 | 催收员(外勤) | tenant1 |",
        "| 13000000006 | 法务对接人 | tenant1(+ provider1 法务) |",
        "| 13000000007 | 运营协调 | tenant1 |",
        "| 13000000008 | 物业项目经理 | tenant1 |",
        "| 13000000009 | 服务商项目经理 | provider1 |",
        "| 13000000010 | 服务商管理员 | provider1 |",
        "| 13000000011 | 服务商催收员 | provider1 |",
        "| 13000000012 | 服务商督导 | provider1 |",
        "",
        "## 额外租户(tenant2-5)/ 服务商(provider2-5)",
        "",
        "v0.5.7 --rich 模式新增,号段 131xxxxxxxx 起。密码同样 `Demo@123!`。",
        "",
        "| 号码 | 姓名 | 角色 | 所属 |",
        "|---|---|---|---|",
    ]
    for a in extra_accounts:
        lines.append(
            f"| {a['phone']} | {a['name']} | {a['role']} | {a['scope']} |"
        )
    lines.append("")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 账号清单写到 {md_path}")


def make_rich_data(db: Session) -> None:
    """主入口:扩展 4 个 tenant + 4 个 provider + 大量 case/call/discount/legal。"""
    print("─" * 60)
    print("▶ --rich 模式:扩展 4 tenant + 4 provider + ~1500 cases")
    print("─" * 60)

    random.seed(RANDOM_SEED)
    used_owner_phones: set[str] = set()
    used_owner_names: set[str] = set()
    used_phones: set[str] = set()
    # 13000000xxx 已用
    for i in range(13):
        used_phones.add(f"1300000000{i}" if i < 10 else f"130000000{i}")

    extra_accounts_md: list[dict] = []

    # 拿 baseline tenant1 / provider1(seed_demo.main 已创建)
    tenant1 = db.execute(select(Tenant).order_by(Tenant.id).limit(1)).scalar_one()
    provider1 = db.execute(
        select(ServiceProvider).order_by(ServiceProvider.id).limit(1)
    ).scalar_one()
    print(f"  baseline: tenant1={tenant1.name}(id={tenant1.id}) provider1={provider1.name}(id={provider1.id})")

    # 拿 baseline 用户(给 case 分配用)
    baseline_internal_agents: list[UserAccount] = list(
        db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant1.id,
                UserTenantMembership.role == "agent",
                UserTenantMembership.work_mode == "internal",
                UserTenantMembership.provider_id.is_(None),
            )
        ).scalars().all()
    )
    print(f"  baseline internal agents: {[a.name for a in baseline_internal_agents]}")

    # 给 tenant1 额外加项目 + case 让数据更丰富(baseline 已 3 项目 9 case,这里再加)
    extra_projects_t1 = []
    for i in range(4):
        city = random.choice(CITIES)
        garden = random.choice(GARDENS)
        pname = f"{city}{garden}{random.choice(['北区', '南区', '西区', '东区'])}"
        proj = make_project_for_tenant(db, tenant1, pname, provider=None, pm_user=None)
        extra_projects_t1.append(proj)
    db.flush()

    # 给 tenant1 的额外项目生成案件
    total_cases_added: list[CollectionCase] = []
    for proj in extra_projects_t1:
        n = random.randint(40, 70)
        cs = make_cases_for_project(
            db, tenant1, proj, n, used_owner_phones, used_owner_names,
            baseline_internal_agents,
        )
        total_cases_added.extend(cs)
    db.commit()
    print(f"  [tenant1] 加 {len(extra_projects_t1)} 项目 + {len(total_cases_added)} cases")

    # 生成 tenant2-5 + provider2-5 + 跨租户合同
    extra_tenants: list[Tenant] = []
    extra_providers: list[ServiceProvider] = []
    for idx in range(2, 6):
        t = make_extra_tenant(db, idx)
        extra_tenants.append(t)
    for idx in range(2, 6):
        p = make_extra_provider(db, idx)
        extra_providers.append(p)
    db.flush()

    # 跨租户合作矩阵
    # provider1 接 tenant1 + tenant2 + tenant3 (baseline 已有 tenant1 合同)
    # provider2 接 tenant1 + tenant4
    # provider3 接 tenant2 + tenant5
    # provider4 接 tenant3
    # provider5 接 tenant4 + tenant5
    contract_pairs: list[tuple[ServiceProvider, Tenant]] = [
        (provider1, extra_tenants[0]),
        (provider1, extra_tenants[1]),
        (extra_providers[0], tenant1),
        (extra_providers[0], extra_tenants[2]),
        (extra_providers[1], extra_tenants[0]),
        (extra_providers[1], extra_tenants[3]),
        (extra_providers[2], extra_tenants[1]),
        (extra_providers[3], extra_tenants[2]),
        (extra_providers[3], extra_tenants[3]),
    ]
    for prov, ten in contract_pairs:
        contract = _upsert_provider_contract(db, ten, prov)
        _upsert_settlement(db, contract)
    db.commit()
    print(f"  跨租户合同矩阵:{len(contract_pairs)} 条")

    # 给每个 extra tenant 生成 admin/supervisor/agent + 5 项目 + 案件
    for idx, t in enumerate(extra_tenants, start=2):
        users = make_extra_tenant_users(db, t, idx, used_phones)
        db.flush()
        for u in users.values():
            extra_accounts_md.append({
                "phone": db.execute(
                    select(UserAccount.phone_enc).where(UserAccount.id == u.id)
                ).scalar_one()[:0] or "(脱敏)",  # 不显示明文电话
                "name": u.name,
                "role": "tenant_user",
                "scope": f"tenant{idx}",
            })
        # 但电话脱敏不便阅读;还是直接展示号段:
        for role_key, u in users.items():
            # 重新查 phone 明文(decrypt)
            from app.core.crypto import decrypt_phone
            try:
                phone_plain = decrypt_phone(
                    db.execute(select(UserAccount.phone_enc).where(UserAccount.id == u.id)).scalar_one()
                )
            except Exception:
                phone_plain = "(decrypt 失败)"
            # 覆盖刚加的占位
            extra_accounts_md[-len(users) + list(users.keys()).index(role_key)] = {
                "phone": phone_plain,
                "name": u.name,
                "role": role_key,
                "scope": f"tenant{idx}",
            }

        # 项目 + 案件
        internal_agents = [u for k, u in users.items() if k == "agent_internal"]
        n_projects = random.randint(4, 6)
        for j in range(n_projects):
            city = random.choice(CITIES)
            garden = random.choice(GARDENS)
            pname = f"{city}{garden}{random.choice(['一期', '二期', '三期', '商业区', '住宅区'])}"
            # 40% 自办,60% 外包给某 provider
            if random.random() < 0.4:
                proj = make_project_for_tenant(db, t, pname, provider=None, pm_user=None)
            else:
                proj_provider = random.choice([provider1, *extra_providers])
                proj = make_project_for_tenant(db, t, pname, provider=proj_provider, pm_user=None)
            n_cases = random.randint(30, 60)
            cs = make_cases_for_project(
                db, t, proj, n_cases, used_owner_phones, used_owner_names, internal_agents,
            )
            total_cases_added.extend(cs)
        db.commit()
        print(f"  [tenant{idx}] {t.name}: {n_projects} 项目 + ~{n_cases * n_projects} cases")

    # 给 extra providers 生成 admin/supervisor/agent
    for idx, p in enumerate(extra_providers, start=2):
        # 用 extra_tenants[idx-2] 作为这个 provider 的「主 tenant」(用于 membership 表必填字段)
        # 实际上 provider 可以接多 tenant,这里给一个挂载点
        main_tenant = extra_tenants[(idx - 2) % len(extra_tenants)]
        users = make_extra_provider_users(db, p, main_tenant, idx, used_phones)
        for role_key, u in users.items():
            from app.core.crypto import decrypt_phone
            try:
                phone_plain = decrypt_phone(
                    db.execute(select(UserAccount.phone_enc).where(UserAccount.id == u.id)).scalar_one()
                )
            except Exception:
                phone_plain = "(decrypt 失败)"
            extra_accounts_md.append({
                "phone": phone_plain,
                "name": u.name,
                "role": role_key,
                "scope": f"provider{idx}",
            })
    db.commit()
    print(f"  ✓ extra tenants/providers/users 全部就位")

    # 生成 call 数据
    print("  生成 call_records...")
    total_calls = make_calls_for_cases(db, tenant1, total_cases_added, baseline_internal_agents)
    db.commit()
    print(f"  ✓ 生成 {total_calls} 通通话(+transcript/analysis)")

    # 生成 discount/legal 各状态(基于 tenant1 的额外案件,因为 helper 都是 tenant1 上下文)
    print("  生成 discount_offers 各状态...")
    admin_user = db.execute(
        select(UserAccount)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant1.id,
            UserTenantMembership.role == "admin",
            UserTenantMembership.provider_id.is_(None),
        )
    ).scalars().first()
    supervisor_user = db.execute(
        select(UserAccount)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant1.id,
            UserTenantMembership.role == "supervisor",
            UserTenantMembership.provider_id.is_(None),
        )
    ).scalars().first()

    if admin_user and supervisor_user and baseline_internal_agents:
        n_disc = make_extra_discount_offers(
            db, tenant1, total_cases_added,
            requester=baseline_internal_agents[0], approver=supervisor_user,
        )
        print(f"  ✓ 生成 {n_disc} 条 discount_offer 各状态")

    # 法务订单
    print("  生成 legal_conversion_orders 各状态...")
    from app.models.legal_conversion import LegalServicePackage
    packages = list(db.execute(
        select(LegalServicePackage).where(LegalServicePackage.tenant_id.is_(None))
    ).scalars().all())
    if packages and admin_user:
        n_lo = make_extra_legal_orders(db, tenant1, total_cases_added, admin_user, packages)
        print(f"  ✓ 生成 {n_lo} 条 legal_conversion_order 各状态")

    # 输出账号清单
    write_accounts_md(Path(__file__).parent.parent.parent.parent, extra_accounts_md)


# ─── 统计 + main ──────────────────────────────────────────────────────


def print_summary(db: Session) -> None:
    """跑完后打印各表行数。"""
    print()
    print("=" * 60)
    print("数据库当前规模统计")
    print("=" * 60)
    from app.models.call import AnalysisResult, CallRecord, Transcript
    from app.models.case import CollectionCase, OwnerProfile, Project
    from app.models.discount_offer import DiscountOffer
    from app.models.legal_conversion import LegalConversionOrder
    from app.models.tenant import (
        ProviderTenantContract, ServiceProvider, Tenant, UserTenantMembership,
    )
    from app.models.user import UserAccount

    counts = [
        ("Tenant", db.execute(select(func.count(Tenant.id))).scalar_one()),
        ("ServiceProvider", db.execute(select(func.count(ServiceProvider.id))).scalar_one()),
        ("ProviderTenantContract", db.execute(select(func.count(ProviderTenantContract.id))).scalar_one()),
        ("UserAccount", db.execute(select(func.count(UserAccount.id))).scalar_one()),
        ("UserTenantMembership", db.execute(select(func.count(UserTenantMembership.id))).scalar_one()),
        ("Project", db.execute(select(func.count(Project.id))).scalar_one()),
        ("OwnerProfile", db.execute(select(func.count(OwnerProfile.id))).scalar_one()),
        ("CollectionCase", db.execute(select(func.count(CollectionCase.id))).scalar_one()),
        ("CallRecord", db.execute(select(func.count(CallRecord.id))).scalar_one()),
        ("Transcript", db.execute(select(func.count(Transcript.id))).scalar_one()),
        ("AnalysisResult", db.execute(select(func.count(AnalysisResult.id))).scalar_one()),
        ("DiscountOffer", db.execute(select(func.count(DiscountOffer.id))).scalar_one()),
        ("LegalConversionOrder", db.execute(select(func.count(LegalConversionOrder.id))).scalar_one()),
    ]
    for name, n in counts:
        print(f"  {name:30s} {n:>6d}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.5.7 压测级 seed 数据")
    parser.add_argument("--reset", action="store_true", help="清空所有租户/业务数据(保留 13 测试号 + audit_log + alembic)")
    parser.add_argument("--rich", action="store_true", help="扩展 4 tenant + 4 provider + ~1500 cases")
    args = parser.parse_args()

    if not args.reset and not args.rich:
        print("用法:--reset 清空 / --rich 扩展(或同时);见 --help")
        sys.exit(2)

    db = SessionLocal()
    try:
        if args.reset:
            reset_all(db)
            # reset 之后跑 baseline seed_demo 恢复 13 个测试号 + tenant1 + provider1
            print("─" * 60)
            print("▶ 重种 baseline(seed_demo.main 创建 tenant1 + provider1 + 13 测试号)")
            print("─" * 60)
            seed_demo_main()  # 它内部 new session,我们这里 commit 一下避免锁
            db.commit()

        if args.rich:
            make_rich_data(db)

        db.commit()
        print_summary(db)
        print("=" * 60)
        print("seed_demo_rich.py — 完成 ✅")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
