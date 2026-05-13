"""seed_demo_v14.py — v1.4 治理增量 demo 数据

在 seed_demo.py + seed_demo_extra.py 跑完之后再跑此脚本，注入：

- 3 个新项目（含一个已结束 + 一个无服务商 + 一个开了 allow_internal_assist 的）
- 一个 pending termination_request 的合同（admin 端「等待对方确认」 / provider 端「收到申请」banner）
- 一个 ops 待审核的服务商（recommended_by_tenant_id 设为 demo 物业，溯源人=Demo 物业）
- 5 条物业私有话术 + 3 条服务商私有话术（覆盖三层来源 badge）
- 30 个新案件分布到新项目（不同 stage / 金额 / 楼栋）
- 给现有 17 个 case 加更多审计事件（让 timeline 更丰富）
- 更多通话记录（覆盖更多 result_tag、agent、时间分布）

幂等：所有 insert 前都查存在性，重复运行不会重复插入。

用法：
    PYTHONPATH=. python3 -m scripts.seed_demo_v14
"""
from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.project_member import ProjectMember
from app.models.script import ScriptTemplate
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    Tenant,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.services.audit import log_audit


def _phone_already_seen(phones: set[str], phone: str) -> bool:
    if phone in phones:
        return True
    phones.add(phone)
    return False


# ─── 新项目 ───────────────────────────────────────────────

NEW_PROJECTS = [
    {
        "name": "金桂园 2026 第二季度催收",
        "status": "active",
        "description": "Q2 重点项目，覆盖 1-3 栋，目标回款率 60%。",
        "with_provider": True,
        "allow_internal_assist": True,
    },
    {
        "name": "翠湖湾电梯维护基金催收",
        "status": "active",
        "description": "电梯维护基金筹集，覆盖 350 户业主。",
        "with_provider": False,
        "allow_internal_assist": False,
    },
    {
        "name": "金桂园 2025 年欠费清理 (已结案)",
        "status": "closed",
        "description": "2025 年遗留案件清理，已于 2026-03 结项。",
        "with_provider": True,
        "allow_internal_assist": False,
    },
]

# ─── 新案件（30 个，分布到 5 个项目 round-robin）────────────
NEW_CASES = [
    # (name, phone, building, room, amount, months, stage)
    ("林志强", "13855111001", "1栋", "0501", "9800", 8, "new"),
    ("徐丽华", "13955111002", "1栋", "1203", "4200", 3, "in_progress"),
    ("黄海波", "13855111003", "2栋", "0405", "7560", 6, "promised"),
    ("张鹏飞", "13755111004", "2栋", "1908", "11200", 9, "escalated"),
    ("李慧敏", "13655111005", "3栋", "0303", "3360", 2, "new"),
    ("王志刚", "13955111006", "3栋", "1502", "5880", 5, "in_progress"),
    ("赵明华", "13855111007", "4栋", "0701", "8400", 7, "promised"),
    ("钱晓东", "13755111008", "4栋", "2106", "16800", 14, "escalated"),
    ("孙美玲", "13655111009", "5栋", "0502", "2520", 2, "paid"),
    ("周建华", "13955111010", "5栋", "1404", "6720", 5, "in_progress"),
    ("吴小敏", "13855111011", "6栋", "0903", "12600", 10, "promised"),
    ("郑海燕", "13755111012", "6栋", "1701", "4480", 4, "new"),
    ("冯志远", "13655111013", "7栋", "0606", "9520", 8, "in_progress"),
    ("陈晓红", "13955111014", "7栋", "1805", "21000", 17, "escalated"),
    ("褚军", "13855111015", "1栋", "0902", "3920", 3, "in_progress"),
    ("卫敏", "13755111016", "2栋", "1502", "7280", 6, "promised"),
    ("沈大鹏", "13655111017", "3栋", "1804", "11760", 10, "in_progress"),
    ("韩晓莉", "13955111018", "4栋", "0203", "5040", 4, "new"),
    ("杨建军", "13855111019", "5栋", "1106", "18480", 15, "escalated"),
    ("朱红梅", "13755111020", "6栋", "0707", "2800", 2, "paid"),
    ("秦志斌", "13655111021", "7栋", "1305", "8960", 7, "in_progress"),
    ("许丽芳", "13955111022", "1栋", "1604", "13440", 11, "promised"),
    ("何文静", "13855111023", "2栋", "0805", "4760", 4, "new"),
    ("吕海涛", "13755111024", "3栋", "2002", "16800", 14, "escalated"),
    ("施美华", "13655111025", "4栋", "1202", "6160", 5, "in_progress"),
    ("张慧君", "13955111026", "5栋", "0503", "9240", 7, "promised"),
    ("孔令辉", "13855111027", "6栋", "1404", "3780", 3, "new"),
    ("曹海波", "13755111028", "7栋", "0807", "10920", 9, "in_progress"),
    ("严国华", "13655111029", "1栋", "2105", "22680", 18, "escalated"),
    ("华文清", "13955111030", "2栋", "0303", "5320", 4, "promised"),
]

# ─── 物业私有话术（5 条，本租户 admin 可改）───────────────
TENANT_SCRIPTS = [
    (
        "本物业-电梯维修标准回应",
        "服务不满",
        "您反映电梯问题我们已记录。本物业在每周二/周五对电梯进行例检，故障 2 小时内响应。"
        "您今天提到的具体故障，我会同步给工程部，48 小时内给您正式答复。物业费的部分能否先按合同缴纳？",
        "针对金桂园电梯老化导致拒缴的高发对话",
    ),
    (
        "本物业-绿化与公共维护安抚",
        "服务不满",
        "您说的绿化问题我了解。本季度物业新增了花艺供应商，您下次回家时留意一下中庭新栽的桂花。"
        "公共区域维护是物业费的一部分，您如果暂时手紧，我们可以分 2 期缴纳？",
        "应对金桂园对绿化不满的中级异议",
    ),
    (
        "本物业-停车位涨价沟通",
        "其他",
        "今年的停车位调价是业委会一致通过的，调价主要用于地库整修。"
        "停车位费用与物业费独立，可以分开缴纳。您方便先把物业费部分处理一下吗？",
        "针对停车位调价引发的拒缴",
    ),
    (
        "本物业-空置房物业费减免询问",
        "经济困难",
        "我们物业的政策是：连续空置 6 个月以上可以申请 30% 减免，您家是这种情况吗？"
        "如果是，我们走减免流程；如果不是，我们看是否分期。",
        "金桂园对空置房减免政策的官方话术",
    ),
    (
        "本物业-业主投诉转工单话术",
        "服务不满",
        "您反映的问题非常具体，我现在为您开一张工单，工单号会发短信给您。"
        "工单专员会在 24 小时内联系您，物业费缴纳时间我们可以等工单进展再确认。",
        "投诉转工单的标准过渡话术",
    ),
]

# ─── 服务商私有话术（3 条，外勤 + 服务商 admin 可见）──────
PROVIDER_SCRIPTS = [
    (
        "聚英-外勤话术-初次联系",
        "其他",
        "您好，我是有证慧催的合作专员，受金桂园物业委托与您联系。"
        "请放心，我们的通话依法录音留证。简单了解一下您的情况：欠费部分有什么困难吗？",
        "服务商外勤标准开场，强调合规录音建立信任",
    ),
    (
        "聚英-法务前置警示",
        "拒缴",
        "我必须告诉您，您当前欠费金额较大，物业按程序会进入法务流程。"
        "一旦产生律师函成本（约 1000-2000 元）和诉讼费，最终都会由您承担。"
        "我们这次沟通的目的就是给您一次窗口期，您愿意试着分期吗？",
        "外勤面对长期拒缴时的硬性话术，金额阈值后使用",
    ),
    (
        "聚英-服务质量改善承诺",
        "服务不满",
        "您提到的物业服务问题我会逐字记录上报本案管理团队。"
        "作为催收专员，我无法替物业承诺，但可以承诺我会在 3 个工作日内给您一个反馈。"
        "您能否在反馈给到之前先预留一笔小额诚意款？",
        "服务商外勤维护客户关系的转化话术",
    ),
]


def upsert_project(
    db, tenant: Tenant, body: dict, provider: ServiceProvider | None,
    pm_property: UserAccount | None, pm_provider: UserAccount | None,
) -> Project:
    p = db.execute(
        select(Project).where(
            Project.tenant_id == tenant.id, Project.name == body["name"]
        )
    ).scalar_one_or_none()
    if p:
        return p
    plan_start = datetime.now(UTC) - timedelta(days=60)
    plan_end = datetime.now(UTC) + timedelta(days=90)
    if body["status"] == "closed":
        plan_end = datetime.now(UTC) - timedelta(days=30)
    p = Project(
        tenant_id=tenant.id,
        name=body["name"],
        provider_id=provider.id if (provider and body["with_provider"]) else None,
        property_pm_user_id=pm_property.id if pm_property else None,
        provider_pm_user_id=pm_provider.id
        if (pm_provider and body["with_provider"]) else None,
        plan_start=plan_start,
        plan_end=plan_end,
        status=body["status"],
        description=body["description"],
        allow_internal_assist=body["allow_internal_assist"],
    )
    db.add(p)
    db.flush()
    print(f"[project +] {p.name} (status={p.status}, provider={p.provider_id})")
    return p


def upsert_owner_case(
    db, tenant: Tenant, project: Project, name: str, phone: str,
    bld: str, room: str, amount: str, months: int, stage: str,
) -> tuple[OwnerProfile, CollectionCase] | None:
    enc = encrypt_phone(phone)
    o = db.execute(
        select(OwnerProfile).where(
            OwnerProfile.tenant_id == tenant.id, OwnerProfile.phone_enc == enc
        )
    ).scalar_one_or_none()
    if o is None:
        o = OwnerProfile(
            tenant_id=tenant.id,
            name=name,
            phone_enc=enc,
            building=bld,
            room=room,
        )
        db.add(o)
        db.flush()
    c = db.execute(
        select(CollectionCase).where(
            CollectionCase.tenant_id == tenant.id, CollectionCase.owner_id == o.id
        )
    ).scalar_one_or_none()
    if c is None:
        c = CollectionCase(
            tenant_id=tenant.id,
            project_id=project.id,
            owner_id=o.id,
            pool_type="public",
            stage=stage,
            amount_owed=Decimal(amount),
            months_overdue=months,
            priority_score=min(months * 6, 99),
            status="active",
        )
        db.add(c)
        db.flush()
        print(f"[case +] {name} {bld}{room} ¥{amount} stage={stage} project={project.id}")
    return o, c


def upsert_script(
    db,
    title: str,
    intent: str,
    content: str,
    notes: str,
    tenant_id: int | None,
    provider_id: int | None,
    creator_id: int | None,
) -> ScriptTemplate | None:
    existing = db.execute(
        select(ScriptTemplate).where(ScriptTemplate.title == title)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    s = ScriptTemplate(
        tenant_id=tenant_id,
        provider_id=provider_id,
        title=title,
        trigger_intent=intent,
        content=content,
        notes=notes,
        version=1,
        is_active=True,
        created_by=creator_id,
    )
    db.add(s)
    db.flush()
    layer = (
        "platform" if (tenant_id is None and provider_id is None)
        else "tenant" if provider_id is None else "provider"
    )
    print(f"[script +] {title} (layer={layer})")
    return s


def main() -> None:
    db = SessionLocal()
    try:
        random.seed(2026)

        # ── 1. 找 demo 租户 + 关键用户 ──────────────────────
        tenant = db.execute(
            select(Tenant).where(Tenant.credit_code.like("DEMO%"))
        ).scalars().first()
        if not tenant:
            tenant = db.execute(select(Tenant).where(Tenant.id == 1)).scalar_one_or_none()
        if not tenant:
            print("ERROR: 没找到 demo 租户；请先跑 seed_demo.py")
            sys.exit(1)
        # 给 tenant 设 18 位 credit_code 便于登录测试
        if not tenant.credit_code or len(tenant.credit_code) != 18:
            tenant.credit_code = "91110000ABCDEF1234"
            print(f"[tenant] credit_code -> {tenant.credit_code}")
        print(f"==> tenant: {tenant.name} (id={tenant.id})")

        admin_user = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role == "admin",
            )
        ).scalars().first()

        pm_property = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role == "project_manager_property",
            )
        ).scalars().first()

        pm_provider = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role == "project_manager_provider",
            )
        ).scalars().first()

        provider_admin = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(UserTenantMembership.role == "provider_admin")
        ).scalars().first()

        # 主签约服务商（聚英）
        main_provider = db.execute(
            select(ServiceProvider).where(
                ServiceProvider.audit_status == "approved"
            ).order_by(ServiceProvider.id)
        ).scalars().first()
        if not main_provider:
            print("WARN: 没找到已审核服务商；跳过 provider 相关数据")

        # ── 2. 推荐入驻：一家 ops 待审核的服务商 ─────────────
        rec_name = "金桂催收服务有限公司（推荐入驻）"
        existing_rec = db.execute(
            select(ServiceProvider).where(ServiceProvider.name == rec_name)
        ).scalar_one_or_none()
        if not existing_rec:
            rec = ServiceProvider(
                name=rec_name,
                provider_type="collection",
                admin_phone_enc=encrypt_phone("13900009998"),
                contact_email="hello@jingui-collect.com",
                description="本地化催收团队，2018 年成立，专注物业费及楼盘业委会催收业务。",
                is_active=True,
                audit_status="pending",
                recommended_by_tenant_id=tenant.id,
            )
            db.add(rec)
            db.flush()
            log_audit(
                db,
                actor_user_id=admin_user.id if admin_user else None,
                actor_role="admin",
                tenant_id=tenant.id,
                action="provider.recommended",
                target_type="service_provider",
                target_id=rec.id,
                payload={"name": rec.name},
            )
            print(f"[provider +] {rec_name} (audit_status=pending, recommended_by={tenant.id})")

        # ── 3. 三个新项目 ──────────────────────────────────
        projects: list[Project] = []
        for body in NEW_PROJECTS:
            p = upsert_project(
                db, tenant, body,
                provider=main_provider, pm_property=pm_property,
                pm_provider=pm_provider,
            )
            projects.append(p)

        # 也包含原有 2 个项目，做新案件分布
        all_projects = db.execute(
            select(Project).where(
                Project.tenant_id == tenant.id, Project.status == "active"
            ).order_by(Project.id)
        ).scalars().all()

        # ── 3a. v1.5.7 — 给「督导小李」加 agent_internal + coordinator 多角色 ──
        # 让督导小李(13000000003)既是督导，又能切换为内勤催收员、协调员，方便测试多 membership UI
        supervisor_user = db.execute(
            select(UserAccount).where(UserAccount.name == "督导小李")
        ).scalar_one_or_none()
        if supervisor_user:
            for extra_role in ["agent_internal", "coordinator"]:
                exists = db.execute(
                    select(UserTenantMembership).where(
                        UserTenantMembership.user_id == supervisor_user.id,
                        UserTenantMembership.tenant_id == tenant.id,
                        UserTenantMembership.role == extra_role,
                    )
                ).scalar_one_or_none()
                if exists is None:
                    db.add(UserTenantMembership(
                        user_id=supervisor_user.id,
                        tenant_id=tenant.id,
                        role=extra_role,
                        source_type="INTERNAL",
                        is_active=True,
                    ))
                    print(f"[membership +] 督导小李 +{extra_role}")
            db.flush()

        # ── 3b. v1.5.6 — 给所有项目绑定协调员 + 法务对接人 ───
        # 任意项目（自办 + 外包）都必须有这两个 ProjectMember 行
        coordinator_user = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role.in_(["coordinator", "workorder"]),
                UserTenantMembership.is_active.is_(True),
            )
        ).scalars().first()
        legal_user = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role == "legal",
                UserTenantMembership.is_active.is_(True),
            )
        ).scalars().first()
        for proj in all_projects:
            for uid, role in [
                (coordinator_user.id if coordinator_user else None, "coordinator"),
                (legal_user.id if legal_user else None, "legal"),
            ]:
                if uid is None:
                    continue
                exists = db.execute(
                    select(ProjectMember).where(
                        ProjectMember.project_id == proj.id,
                        ProjectMember.role_in_project == role,
                        ProjectMember.is_active.is_(True),
                    )
                ).scalar_one_or_none()
                if exists is None:
                    db.add(ProjectMember(
                        project_id=proj.id,
                        user_id=uid,
                        role_in_project=role,
                        is_active=True,
                    ))
                    print(f"[project_member +] project={proj.id} user={uid} role={role}")
        db.flush()

        # ── 4. 30 个新案件（round-robin 分到活跃项目）──────
        seen_phones: set[str] = set()
        new_case_ids: list[int] = []
        for i, (name, phone, bld, room, amount, months, stage) in enumerate(NEW_CASES):
            if _phone_already_seen(seen_phones, phone):
                continue
            project = all_projects[i % len(all_projects)]
            result = upsert_owner_case(
                db, tenant, project, name, phone, bld, room, amount, months, stage
            )
            if result:
                _, c = result
                new_case_ids.append(c.id)

        # ── 5. 三层话术：5 物业 + 3 服务商 ─────────────────
        creator_id = admin_user.id if admin_user else None
        provider_creator = provider_admin.id if provider_admin else None
        for title, intent, content, notes in TENANT_SCRIPTS:
            upsert_script(
                db, title, intent, content, notes,
                tenant_id=tenant.id, provider_id=None, creator_id=creator_id,
            )
        if main_provider:
            for title, intent, content, notes in PROVIDER_SCRIPTS:
                upsert_script(
                    db, title, intent, content, notes,
                    tenant_id=None, provider_id=main_provider.id,
                    creator_id=provider_creator,
                )

        # ── 6. 一个 pending termination_request 的合同 ──────
        if main_provider:
            contract = db.execute(
                select(ProviderTenantContract).where(
                    ProviderTenantContract.tenant_id == tenant.id,
                    ProviderTenantContract.provider_id == main_provider.id,
                )
            ).scalar_one_or_none()
            if contract and contract.status == "active":
                if contract.termination_requested_at is None:
                    # 物业 3 天前发起，服务商还没确认 → admin 看到「等待对方确认」
                    # provider 看到「收到解约申请，剩 4 天」
                    contract.termination_requested_by = 1  # property
                    contract.termination_requested_at = (
                        datetime.now(UTC) - timedelta(days=3)
                    )
                    contract.termination_reason = "demo: 服务质量未达预期，启动协商解约。"
                    log_audit(
                        db,
                        actor_user_id=admin_user.id if admin_user else None,
                        actor_role="admin",
                        tenant_id=tenant.id,
                        action="provider.contract.terminate_requested",
                        target_type="provider_tenant_contract",
                        target_id=contract.id,
                        payload={"by": "property", "reason": contract.termination_reason},
                    )
                    print(
                        f"[contract] 已发起解约请求（contract_id={contract.id}）"
                        f"剩 {7 - 3} 天等待对方确认"
                    )

        # ── 7. 给 v1.4 创建的新案件加审计事件丰富 timeline ──
        agents = db.execute(
            select(UserAccount)
            .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
            .where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role.in_(("agent_internal", "agent_external")),
                UserTenantMembership.is_active.is_(True),
            )
        ).scalars().all()

        new_cases = db.execute(
            select(CollectionCase).where(
                CollectionCase.id.in_(new_case_ids),
            )
        ).scalars().all() if new_case_ids else []

        if agents and new_cases:
            for i, c in enumerate(new_cases[:18]):
                # case.assigned
                a = agents[i % len(agents)]
                c.assigned_to = a.id
                c.pool_type = "private"
                log_audit(
                    db,
                    actor_user_id=admin_user.id if admin_user else a.id,
                    actor_role="admin",
                    tenant_id=tenant.id,
                    action="case.assigned",
                    target_type="case",
                    target_id=c.id,
                    payload={"assignee_id": a.id, "assignee_name": a.name},
                )
                # 一半案件再加阶段流转事件
                if i % 2 == 0 and c.stage in ("in_progress", "promised", "escalated"):
                    log_audit(
                        db,
                        actor_user_id=a.id,
                        actor_role="agent_internal",
                        tenant_id=tenant.id,
                        action="case.stage_changed",
                        target_type="case",
                        target_id=c.id,
                        payload={"from": "new", "to": c.stage},
                    )

        # ── 8. 给 admin_user 设邮箱（演示邮箱登录） ────────
        if admin_user and not admin_user.email:
            admin_user.email = "admin@demo-property.com"
            print(f"[user] admin email -> {admin_user.email}")

        db.commit()
        print("=" * 60)
        print("seed_demo_v14.py — 全部写入完成 ✅")
        print(f"  项目: {len(projects)} 个新建")
        print(f"  案件: {len(new_case_ids)} 个新增")
        print(f"  话术: {len(TENANT_SCRIPTS)} 物业 + "
              f"{len(PROVIDER_SCRIPTS) if main_provider else 0} 服务商")
        print(f"  合同解约请求: pending（admin/provider 端均有 banner）")
        print(f"  推荐服务商: 1 家 audit_status=pending（ops 端可见）")
        print("=" * 60)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
