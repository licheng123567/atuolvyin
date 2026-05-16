"""seed_demo_extra.py — 丰富 Demo 数据（在 seed_demo.py 基础上补充）

用法：
    PYTHONPATH=. python3 -m scripts.seed_demo_extra

幂等：所有 insert 前都检查存在性。
本脚本注入：
- 5 个真实催收员（李小红 / 王芳芳 / 张建华 / 陈明远 / 刘晓娟）作为 agent_internal
  补全后台排名表 / 用户管理页面的 demo 数据
- 12 个新业主与对应案件（含不同欠费金额和阶段）
- ~30 通通话记录（分布到 3 天，5 个坐席，含不同 result_tag）
- 对应 AnalysisResult（intent + confidence + summary）
- ~6 条 RiskEvent（L1×3 / L2×2 / L3×1）
- TenantMinuteUsage 当月已用量
- 3 个 WorkOrder
"""
from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.models.call import AnalysisResult, CallRecord, RiskEvent, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import (
    Tenant,
    TenantMinuteUsage,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.models.work import LegalCase, WorkOrder
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.services.audit import log_audit

DEMO_PASSWORD = "Demo@123!"

# ── 5 个 demo 催收员 ──────────────────────────────────────
EXTRA_AGENTS = [
    ("13800001001", "李小红"),
    ("13800001002", "王芳芳"),
    ("13800001003", "张建华"),
    ("13800001004", "陈明远"),
    ("13800001005", "刘晓娟"),
]

# ── 12 个新业主 + 案件 (name, phone, building, room, amount_owed, months, stage) ─
EXTRA_OWNERS = [
    ("张大伟", "13866216621", "3栋", "1201", "8420", 7, "in_progress"),
    ("刘美华", "13922082208", "1栋", "0803", "12600", 10, "new"),
    ("王建国", "13788438843", "5栋", "2201", "5040", 4, "promised"),
    ("陈小燕", "13511229933", "2栋", "0601", "21000", 17, "escalated"),
    ("孙志远", "13599887766", "4栋", "1504", "3360", 3, "in_progress"),
    ("赵云霞", "13677889911", "6栋", "0901", "16800", 14, "escalated"),
    ("李建明", "13788441122", "1栋", "0302", "2520", 2, "paid"),
    ("周晓敏", "13433226677", "3栋", "0704", "6300", 5, "new"),
    ("吴大强", "13211009988", "7栋", "1801", "25200", 21, "in_progress"),
    ("马晓芳", "13955667788", "2栋", "1103", "4200", 3, "promised"),
    ("郑海涛", "13066778899", "5栋", "0506", "9660", 8, "in_progress"),
    ("何敏华", "13899221133", "4栋", "2002", "18480", 15, "escalated"),
]


def upsert_user(db, phone: str, name: str) -> tuple[UserAccount, bool]:
    enc = encrypt_phone(phone)
    existing = db.execute(
        select(UserAccount).where(UserAccount.phone_enc == enc)
    ).scalar_one_or_none()
    if existing:
        return existing, False
    u = UserAccount(
        phone_enc=enc,
        name=name,
        password_hash=get_password_hash(DEMO_PASSWORD),
        is_active=True,
    )
    db.add(u)
    db.flush()
    print(f"[created] UserAccount: {name} ({phone}) id={u.id}")
    return u, True


def upsert_membership(
    db, user: UserAccount, tenant: Tenant, role: str,
    *, work_mode: str | None = None,
) -> None:
    existing = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant.id,
            UserTenantMembership.role == role,
        )
    ).scalar_one_or_none()
    if existing:
        return
    m = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=role,
        work_mode=work_mode,
        is_active=True,
    )
    db.add(m)
    db.flush()
    print(f"[created] Membership: {user.name} -> {role}")


def upsert_owner_case(
    db, tenant: Tenant, name: str, phone: str, building: str, room: str,
    amount: str, months: int, stage: str
) -> tuple[OwnerProfile, CollectionCase]:
    enc = encrypt_phone(phone)
    owner = db.execute(
        select(OwnerProfile).where(
            OwnerProfile.tenant_id == tenant.id,
            OwnerProfile.phone_enc == enc,
        )
    ).scalar_one_or_none()
    if not owner:
        owner = OwnerProfile(
            tenant_id=tenant.id,
            name=name,
            phone_enc=enc,
            building=building,
            room=room,
        )
        db.add(owner)
        db.flush()
        print(f"[created] OwnerProfile: {name}")
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.tenant_id == tenant.id,
            CollectionCase.owner_id == owner.id,
        )
    ).scalar_one_or_none()
    if not case:
        # 优先级 = 欠费月数 × 5 + 金额万分位
        priority = months * 5 + int(int(amount) / 100)
        case = CollectionCase(
            tenant_id=tenant.id,
            owner_id=owner.id,
            pool_type="public" if stage == "new" else "private",
            stage=stage,
            amount_owed=Decimal(amount),
            months_overdue=months,
            priority_score=priority,
        )
        db.add(case)
        db.flush()
        print(f"[created] CollectionCase: {name} → ¥{amount} ({stage})")
    return owner, case


def maybe_create_call(
    db,
    tenant: Tenant,
    case: CollectionCase,
    owner: OwnerProfile,
    agent: UserAccount,
    started_at: datetime,
    duration_sec: int,
    result_tag: str | None,
    intent: str | None,
    confidence: float | None,
    summary: str | None,
    risk: tuple[str, str, str] | None = None,  # (level, category, trigger_text)
) -> CallRecord | None:
    """在指定时间点为 (case, agent) 注入一通电话；如该 agent 已有同时间点通话则跳过。"""
    existing = db.execute(
        select(CallRecord).where(
            CallRecord.tenant_id == tenant.id,
            CallRecord.case_id == case.id,
            CallRecord.caller_user_id == agent.id,
            CallRecord.started_at == started_at,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    call = CallRecord(
        tenant_id=tenant.id,
        case_id=case.id,
        caller_user_id=agent.id,
        callee_phone_enc=owner.phone_enc,
        initiated_by="app",
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=duration_sec),
        duration_sec=duration_sec,
        billable_duration=max(0, duration_sec - 5),
        result_tag=result_tag,
        risk_flagged=bool(risk),
        status="processed" if intent else "uploaded",
        recording_mode="post",
    )
    db.add(call)
    db.flush()

    # Transcript: 占位 mock 文本
    if intent:
        db.add(Transcript(
            call_id=call.id,
            full_text=summary or "（占位转写）",
            asr_model="mock",
        ))

        # AnalysisResult
        db.add(AnalysisResult(
            call_id=call.id,
            summary=summary,
            key_segments={
                "intent": intent,
                "confidence": confidence,
                "transcript_preview": summary,
            },
            followup_suggestion=("建议 3 天内回访" if intent == "promise_made" else None),
            llm_model="mock",
        ))

    if risk:
        level, category, trigger = risk
        intervention = "warn" if level == "L1" else ("interrupt" if level == "L2" else "terminate")
        db.add(RiskEvent(
            call_id=call.id,
            level=level,
            category=category,
            trigger_text=trigger,
            audio_offset_ms=int(duration_sec * 1000 * 0.4),
            intervention=intervention,
        ))

    print(f"[created] CallRecord: {agent.name} → {owner.name} ({duration_sec}s, {intent or 'pending'})")
    return call


def upsert_minute_usage(db, tenant: Tenant, used: int, realtime: int) -> None:
    ym = datetime.now(UTC).strftime("%Y-%m")
    existing = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant.id,
            TenantMinuteUsage.year_month == ym,
        )
    ).scalar_one_or_none()
    if existing:
        existing.used_minutes = used
        existing.realtime_minutes = realtime
        existing.post_minutes = used - realtime
        print(f"[updated] TenantMinuteUsage {ym}: {used} 分钟")
        return
    db.add(TenantMinuteUsage(
        tenant_id=tenant.id,
        year_month=ym,
        used_minutes=used,
        realtime_minutes=realtime,
        post_minutes=used - realtime,
        quota_at_time=tenant.monthly_minute_quota,
    ))
    print(f"[created] TenantMinuteUsage {ym}: {used} 分钟")


def maybe_create_work_order(
    db, tenant: Tenant, case: CollectionCase, agent: UserAccount,
    desc: str, status: str, priority: str
) -> None:
    existing = db.execute(
        select(WorkOrder).where(
            WorkOrder.tenant_id == tenant.id,
            WorkOrder.case_id == case.id,
            WorkOrder.description == desc,
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(WorkOrder(
        tenant_id=tenant.id,
        case_id=case.id,
        order_type="case_followup",
        description=desc,
        assigned_to=agent.id,
        status=status,
        priority=priority,
    ))
    print(f"[created] WorkOrder: {desc[:30]}…")


def upsert_legal_package(db) -> LegalServicePackage:
    """平台级（tenant_id IS NULL）律师函服务包，幂等。"""
    pkg = db.execute(
        select(LegalServicePackage).where(
            LegalServicePackage.tenant_id.is_(None),
            LegalServicePackage.slug == "lawyer_letter_basic",
        )
    ).scalar_one_or_none()
    if pkg:
        return pkg
    pkg = LegalServicePackage(
        tenant_id=None,
        slug="lawyer_letter_basic",
        package_type="lawyer_letter",
        name="律师函（基础版）",
        description="律所开具加盖公章律师函 1 份，含 EMS 邮寄。",
        price=Decimal("680.00"),
        platform_fee_rate=Decimal("0.25"),
        enabled=True,
        sort_order=10,
    )
    db.add(pkg)
    db.flush()
    print(f"[created] LegalServicePackage: {pkg.name} id={pkg.id}")
    return pkg


def maybe_create_conversion(
    db, tenant: Tenant, case: CollectionCase, package: LegalServicePackage,
    status: str, lawyer_name: str, law_firm: str, days_ago: int,
    creator: UserAccount,
) -> LegalConversionOrder | None:
    """幂等：以 (tenant, case) 为唯一键，已存在则跳过。"""
    existing = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.tenant_id == tenant.id,
            LegalConversionOrder.case_id == case.id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    fee_rate = float(package.platform_fee_rate)
    price = float(package.price)
    when = datetime.now(UTC) - timedelta(days=days_ago)
    order = LegalConversionOrder(
        tenant_id=tenant.id,
        case_id=case.id,
        package_id=package.id,
        status=status,
        price_quoted=Decimal(str(price)),
        platform_fee_amount=Decimal(str(round(price * fee_rate, 2))),
        assigned_law_firm=law_firm,
        assigned_lawyer_name=lawyer_name,
        created_by=creator.id,
        dispatched_at=when if status in ("dispatched", "in_service", "completed") else None,
        completed_at=when if status == "completed" else None,
    )
    order.created_at = when  # 覆盖 server_default 的 now()
    order.updated_at = when
    db.add(order)
    db.flush()
    print(f"[created] LegalConversionOrder: case_id={case.id} status={status}")
    return order


def maybe_create_legal_case(
    db, tenant: Tenant, case: CollectionCase, lawyer_name: str,
    law_firm: str, stage: str, milestone: str, days_ago: int,
) -> None:
    existing = db.execute(
        select(LegalCase).where(
            LegalCase.tenant_id == tenant.id,
            LegalCase.case_id == case.id,
        )
    ).scalar_one_or_none()
    if existing:
        return
    when = datetime.now(UTC) - timedelta(days=days_ago)
    lc = LegalCase(
        tenant_id=tenant.id,
        case_id=case.id,
        stage=stage,
        amount_disputed=case.amount_owed,
        lawyer_name=lawyer_name,
        law_firm=law_firm,
        next_milestone=milestone,
        notes=f"由 demo seed 自动创建（{days_ago} 天前）",
    )
    lc.created_at = when
    lc.updated_at = when
    db.add(lc)
    db.flush()
    print(f"[created] LegalCase: case_id={case.id} stage={stage}")


def maybe_log_case_audit(
    db, tenant: Tenant, case: CollectionCase, actor: UserAccount,
    action: str, payload_extra: dict, days_ago: float,
) -> None:
    """幂等：检查 (tenant, target=case, action, actor) 已存在则跳过。"""
    from app.models.audit import AuditLog
    existing = db.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant.id,
            AuditLog.target_type == "case",
            AuditLog.target_id == case.id,
            AuditLog.action == action,
            AuditLog.actor_user_id == actor.id,
        )
    ).first()
    if existing:
        return
    log_audit(
        db,
        actor_user_id=actor.id,
        actor_role="admin",
        tenant_id=tenant.id,
        action=action,
        target_type="case",
        target_id=case.id,
        payload=payload_extra,
    )
    # 覆盖 created_at（log_audit 写完即 flush，需要 manual update）
    db.flush()
    row = db.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant.id,
            AuditLog.target_type == "case",
            AuditLog.target_id == case.id,
            AuditLog.action == action,
            AuditLog.actor_user_id == actor.id,
        ).order_by(AuditLog.id.desc())
    ).scalars().first()
    if row is not None:
        row.created_at = datetime.now(UTC) - timedelta(days=days_ago)
    print(f"[created] AuditLog: case_id={case.id} {action}")


def main() -> None:
    db = SessionLocal()
    try:
        random.seed(42)  # 保证可复现

        # 1. 找 Demo 租户
        tenant = db.execute(
            select(Tenant).where(Tenant.credit_code == "DEMO000000000001")
        ).scalar_one_or_none()
        if not tenant:
            print("ERROR: Demo 物业 不存在；请先跑 seed_demo.py")
            sys.exit(1)
        print(f"==> 写入 Demo 物业 (id={tenant.id}) 的扩展数据")

        # 2. 5 个新催收员
        agents: list[UserAccount] = []
        for phone, name in EXTRA_AGENTS:
            u, _ = upsert_user(db, phone, name)
            upsert_membership(db, u, tenant, "agent", work_mode="internal")
            agents.append(u)

        # 3. 12 个新业主 + 案件
        cases: list[tuple[CollectionCase, OwnerProfile]] = []
        for name, phone, bld, room, amount, months, stage in EXTRA_OWNERS:
            owner, case = upsert_owner_case(
                db, tenant, name, phone, bld, room, amount, months, stage
            )
            cases.append((case, owner))

        # 3b. 把 project_id 为 NULL 的案件回填到 2 个 demo 项目（round-robin）
        from app.models.case import Project as ProjectModel
        demo_projects = db.execute(
            select(ProjectModel).where(
                ProjectModel.tenant_id == tenant.id,
                ProjectModel.name.in_(["金桂园 2026 年欠费催收", "翠湖湾电梯专项整改"]),
            ).order_by(ProjectModel.id)
        ).scalars().all()
        if demo_projects:
            unassigned = db.execute(
                select(CollectionCase).where(
                    CollectionCase.tenant_id == tenant.id,
                    CollectionCase.project_id.is_(None),
                ).order_by(CollectionCase.id)
            ).scalars().all()
            for i, c in enumerate(unassigned):
                c.project_id = demo_projects[i % len(demo_projects)].id
            if unassigned:
                print(f"[backfill] {len(unassigned)} cases → project_id round-robin")

        # 4. 通话记录 — 30 通分布在过去 3 天
        now = datetime.now(UTC)
        today_start = now.replace(hour=9, minute=0, second=0, microsecond=0)

        # 调用模板：(intent, confidence, summary, risk)
        # intent: promise_made / 推托 / 拒缴 / 立即缴 / 无意愿 / None(无人接)
        templates = [
            ("promise_made", 0.91, "业主表示月底前会想办法缴清欠费。", None),
            ("推托", 0.87, "业主称近期手头紧，老人看病花了不少钱，含糊承诺。", None),
            ("立即缴", 0.95, "业主当场答应立即微信转账缴费。", None),
            ("拒缴", 0.83, "业主以小区物业服务质量为由明确拒绝缴费。", None),
            ("无意愿", 0.78, "电话接通但业主以正在开会为由要求改天再聊。", None),
            ("promise_made", 0.79, "业主承诺下周一前缴清部分欠费。", None),
            ("推托", 0.85, "业主反复表达对绿化与电梯维护不满，未明确承诺。",
                ("L1", "owner_complaint", "你们物业平时都不修电梯！")),
            ("拒缴", 0.88, "业主情绪激动，多次提及『投诉』。",
                ("L2", "owner_threat", "再不解决我就去市政府投诉你们！")),
            ("无意愿", 0.92, "通话仅 30 秒便挂断。", None),
            ("promise_made", 0.94, "业主答应 3 天内缴清。", None),
        ]

        # 3 天 × 每天每坐席 ~2 通
        for day_offset in range(3):
            day = today_start - timedelta(days=day_offset)
            for ai, agent in enumerate(agents):
                for slot in range(2):
                    if not cases:
                        break
                    # 通话时间：9:00 起 + 坐席偏移 + slot 偏移
                    hour = 9 + ai
                    minute = slot * 30
                    started = day.replace(hour=hour, minute=minute)
                    case, owner = random.choice(cases)
                    template = templates[(ai * 2 + slot + day_offset) % len(templates)]
                    intent, conf, summary, risk = template
                    duration = random.choice([60, 90, 120, 180, 240, 300])
                    # 把 intent 翻译到 result_tag
                    tag_map = {
                        "promise_made": "承诺缴",
                        "立即缴": "立即缴",
                        "推托": "推托",
                        "拒缴": "拒缴",
                        "无意愿": "推托",
                    }
                    maybe_create_call(
                        db, tenant, case, owner, agent,
                        started_at=started,
                        duration_sec=duration,
                        result_tag=tag_map.get(intent),
                        intent=intent,
                        confidence=conf,
                        summary=summary,
                        risk=risk,
                    )

        # 5. 一通无人接听通话（status=uploaded, duration < 10）
        if agents and cases:
            case, owner = cases[0]
            maybe_create_call(
                db, tenant, case, owner, agents[0],
                started_at=today_start - timedelta(hours=2),
                duration_sec=8,
                result_tag=None,
                intent=None,
                confidence=None,
                summary=None,
            )

        # 6. 一条 L3 严重风控
        if agents and cases:
            case, owner = cases[3]  # 陈小燕（escalated）
            maybe_create_call(
                db, tenant, case, owner, agents[2],  # 张建华
                started_at=today_start - timedelta(hours=5),
                duration_sec=420,
                result_tag="拒缴",
                intent="拒缴",
                confidence=0.95,
                summary="业主威胁要起诉物业。",
                risk=("L3", "agent_violation", "你再不交我就让你好看"),
            )

        # 7. 当月分钟用量（约 65% 配额，触发"接近上限"提示）
        quota = tenant.monthly_minute_quota or 600
        used = int(quota * 0.65)
        realtime = int(used * 0.4)
        upsert_minute_usage(db, tenant, used=used, realtime=realtime)

        # 8. 3 个工单
        if agents and cases:
            maybe_create_work_order(
                db, tenant, cases[1][0], agents[0],
                "业主反映电梯长期故障，请物业现场处理后再联系", "open", "urgent"
            )
            maybe_create_work_order(
                db, tenant, cases[5][0], agents[1],
                "业主提出按月分期缴费，需要核算分期方案", "in_progress", "normal"
            )
            maybe_create_work_order(
                db, tenant, cases[8][0], agents[2],
                "上次通话录音存疑，请音频质检团队复审", "open", "low"
            )

        # 9. 法务转化（3 个 escalated 案件）+ LegalCase 跟进
        if agents and cases:
            package = upsert_legal_package(db)
            # 找出本租户里 stage='escalated' 的 case
            escalated_cases = db.execute(
                select(CollectionCase).where(
                    CollectionCase.tenant_id == tenant.id,
                    CollectionCase.stage == "escalated",
                ).order_by(CollectionCase.id).limit(3)
            ).scalars().all()
            scenarios = [
                ("pending", "陈志杰", "兴华律师事务所", "等待律所接单", 1, "pending_eval"),
                ("dispatched", "李明阳", "兴华律师事务所", "律师函起草中", 4, "drafting"),
                ("completed", "周晓敏", "兴华律师事务所", "律师函已签收", 12, "letter_sent"),
            ]
            for ec, (status, lawyer, firm, milestone, days, lc_stage) in zip(
                escalated_cases, scenarios
            ):
                maybe_create_conversion(
                    db, tenant, ec, package,
                    status=status, lawyer_name=lawyer, law_firm=firm,
                    days_ago=days, creator=agents[0],
                )
                if status != "pending":
                    maybe_create_legal_case(
                        db, tenant, ec, lawyer, firm,
                        stage=lc_stage, milestone=milestone, days_ago=days,
                    )

        # 10. promised 案件设置 promise_due_at（3~7 天）
        if cases:
            promised_cases = db.execute(
                select(CollectionCase).where(
                    CollectionCase.tenant_id == tenant.id,
                    CollectionCase.stage == "promised",
                ).order_by(CollectionCase.id).limit(5)
            ).scalars().all()
            for i, pc in enumerate(promised_cases):
                if pc.promise_due_at is None:
                    pc.promise_due_at = datetime.now(UTC) + timedelta(days=3 + i)
                    print(f"[set] case_id={pc.id} promise_due_at +{3+i}d")

        # 11. 案件审计事件：assigned / stage_changed / escalated / released
        all_cases = db.execute(
            select(CollectionCase).where(
                CollectionCase.tenant_id == tenant.id
            ).order_by(CollectionCase.id)
        ).scalars().all()
        if agents and len(all_cases) >= 12:
            # case.assigned × 5：5 个 case 各分配给一个 agent
            assignment_pairs = [
                (all_cases[5], agents[0], "李小红"),
                (all_cases[6], agents[1], "王芳芳"),
                (all_cases[7], agents[2], "张建华"),
                (all_cases[9], agents[3], "陈明远"),
                (all_cases[10], agents[4], "刘晓娟"),
            ]
            for case, agent, agent_name in assignment_pairs:
                maybe_log_case_audit(
                    db, tenant, case, agent,
                    action="case.assigned",
                    payload_extra={"assignee_name": agent_name},
                    days_ago=5,
                )

            # case.stage_changed × 10：跟踪几个 case 的阶段流转
            stage_flow = [
                (all_cases[5], "in_progress", agents[0], 4),
                (all_cases[6], "in_progress", agents[1], 4),
                (all_cases[7], "in_progress", agents[2], 4),
                (all_cases[7], "promised", agents[2], 2),
                (all_cases[9], "in_progress", agents[3], 3),
                (all_cases[11], "paid", agents[0], 6),
                (all_cases[14], "promised", agents[1], 1),
                (all_cases[16], "in_progress", agents[3], 8),
                (all_cases[16], "escalated", agents[3], 5),
                (all_cases[8], "promised", agents[2], 1.5),
            ]
            for case, new_stage, agent, days in stage_flow:
                maybe_log_case_audit(
                    db, tenant, case, agent,
                    action="case.stage_changed",
                    payload_extra={"stage": new_stage},
                    days_ago=days,
                )

            # case.escalated × 3
            for case in all_cases[8:11]:
                if case.stage == "escalated":
                    maybe_log_case_audit(
                        db, tenant, case, agents[0],
                        action="case.escalated",
                        payload_extra={"reason": "金额大且联系困难"},
                        days_ago=2,
                    )

            # case.released × 2（释放至公海）
            for case in all_cases[12:14]:
                maybe_log_case_audit(
                    db, tenant, case, agents[2],
                    action="case.released",
                    payload_extra={"reason": "联系不上业主，回流公海"},
                    days_ago=7,
                )

        db.commit()
        print("=" * 60)
        print("seed_demo_extra.py — 全部写入完成 ✅")
        print("=" * 60)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
