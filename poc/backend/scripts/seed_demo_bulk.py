"""seed_demo_bulk.py — 批量补充模拟数据（幂等，可重复跑）。

用法:
    docker exec autoluyin-backend sh -c "cd /app && PYTHONPATH=/app python scripts/seed_demo_bulk.py"

幂等标记:
- discount_offer：reason 里含 [bulk] 的行跳过重复插入
- legal_conversion_request：reason 里含 [bulk] 的行跳过重复插入
- legal_conversion_request_material：object_key 含 'bulk/' 的行跳过
- recording_file：object_key 含 'bulk/' 的行跳过
- collection_promise：note 含 [bulk] 的行跳过
- notification：body 含 [bulk] 的行跳过
- qc_alert：detail 含 [bulk] 的行跳过
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select, text

from app.core.crypto import encrypt_phone
from app.core.db import SessionLocal
from app.models.case import CollectionCase
from app.models.discount_offer import DiscountOffer
from app.models.legal_conversion import (
    LegalConversionRequest,
    LegalConversionRequestMaterial,
)
from app.models.notification import Notification
from app.models.tenant import ServiceProvider, Tenant
from app.models.user import UserAccount

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def _count(db, table_name: str) -> int:
    row = db.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
    return int(row)


def _count_filtered(db, table_name: str, col: str, marker: str) -> int:
    row = db.execute(text(f"SELECT count(*) FROM {table_name} WHERE {col} LIKE :m"), {"m": f"%{marker}%"}).scalar()
    return int(row)


# ────────────────────────────────────────────────
# discount_offer — 补到约 20 条
# ────────────────────────────────────────────────

BULK_DO_DATA = [
    # (case_id, provider_id, applicant_user_id, applicant_role, offer_type, original, pct_off, status, approver_role, reason, installment_months, approver_user_id, rejected_reason)
    # 物业内勤发起 (provider_id=NULL)
    (4,  None, 5, "agent", "principal_discount", Decimal("9100.00"), 20, "pending_supervisor", "supervisor", "业主出示医疗证明，主张家庭困难。[bulk]", None, None, None),
    (5,  None, 5, "agent", "late_fee_waive",      Decimal("2400.00"),  0, "pending_supervisor", "supervisor", "业主长期客户，滞纳金属误解，申请全免。[bulk]", None, None, None),
    (6,  None, 4, "supervisor", "principal_discount", Decimal("18000.00"), 30, "pending_admin", "admin", "商铺业主空置 2 年，提出减免 30% 换一次性缴清。[bulk]", None, None, None),
    (7,  None, 5, "agent", "installment",         Decimal("6800.00"),   0, "approved",          "supervisor", "商铺业主资金周转紧张，申请 3 期分期。[bulk]", 3, 4, None),
    (8,  None, 4, "supervisor", "late_fee_waive",  Decimal("21000.00"),  0, "approved",          "supervisor", "超长欠费业主，滞纳金已全免换本金一次缴清协议。[bulk]", None, 4, None),
    (9,  None, 5, "agent", "principal_discount",  Decimal("4500.00"),  10, "rejected",          "supervisor", "折扣理由不充分，驳回。[bulk]", None, None, "业主欠费理由为主观异议，未提供实质证据，本次申请不批准。"),
    (34, None, 5, "agent", "long_overdue_compromise", Decimal("8420.00"), 15, "pending_supervisor", "supervisor", "欠费超 12 个月，业主愿意折 85% 一次性结清。[bulk]", None, None, None),
    (35, None, 4, "supervisor", "principal_discount", Decimal("12600.00"), 25, "pending_admin", "admin", "业主投诉服务质量，要求减免 25% 才肯缴费。[bulk]", None, None, None),
    (36, None, 5, "agent", "installment",         Decimal("5040.00"),   0, "approved",          "supervisor", "业主工资每月发放，申请 6 期分期。[bulk]", 6, 4, None),
    (37, None, 4, "supervisor", "late_fee_waive",  Decimal("21000.00"),  0, "approved",          "admin",      "大额欠费，滞纳金全免吸引本金回收。[bulk]", None, 3, None),
    (38, None, 5, "agent", "principal_discount",  Decimal("3360.00"),   5, "executed",          "supervisor", "业主已按折扣金额缴清，合同附件存档。[bulk]", None, 4, None),
    # 服务商发起 (provider_id=1)
    (39, 1, 12, "agent", "principal_discount",   Decimal("16800.00"), 20, "pending_supervisor", "supervisor", "服务商催收员介入，业主同意打折换回款。[bulk]", None, None, None),
    (40, 1, 12, "agent", "late_fee_waive",        Decimal("2520.00"),   0, "pending_admin",      "admin",      "服务商协商结果：滞纳金免除，业主 3 日内缴本金。[bulk]", None, None, None),
    (41, 1, 13, "supervisor", "installment",      Decimal("6300.00"),   0, "approved",           "supervisor", "服务商督导审核通过，4 期分期。[bulk]", 4, 13, None),
    (42, 1, 12, "agent", "long_overdue_compromise", Decimal("25200.00"), 20, "approved",         "admin",      "服务商跟进超大额欠费，折让 20% 一次性结清。[bulk]", None, 3, None),
    (43, 1, 13, "supervisor", "principal_discount", Decimal("4200.00"), 10, "rejected",          "admin",      "折扣比例超出项目政策，服务商申请被驳回。[bulk]", None, None, "超出项目级折扣上限（10% > 项目设定 8%），请服务商重新申请。"),
    (44, 1, 12, "agent", "late_fee_waive",        Decimal("9660.00"),   0, "pending_supervisor", "supervisor", "服务商催收员上报：业主要求减免滞纳金方肯出门缴费。[bulk]", None, None, None),
]


def seed_discount_offers(db, tenant: Tenant, supervisor_user: UserAccount, admin_user: UserAccount) -> int:
    inserted = 0
    existing_bulk = _count_filtered(db, "discount_offer", "reason", "[bulk]")
    if existing_bulk > 0:
        print(f"  [skip] discount_offer 已有 {existing_bulk} 条 [bulk] 数据，跳过")
        return 0

    now = datetime.now(timezone.utc)
    for row in BULK_DO_DATA:
        (case_id, provider_id, applicant_uid, applicant_role, offer_type,
         original, pct_off, status, approver_role, reason, installment_months,
         approver_uid, rejected_reason) = row

        # case 是否存在
        case_exists = db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        ).scalar_one_or_none()
        if not case_exists:
            print(f"  [skip] case_id={case_id} 不存在，跳过该条 discount_offer")
            continue

        # 已存在同 case + offer_type 的 bulk 行？（用 reason 标记）
        dup = db.execute(
            select(DiscountOffer).where(
                DiscountOffer.tenant_id == tenant.id,
                DiscountOffer.case_id == case_id,
                DiscountOffer.offer_type == offer_type,
                DiscountOffer.reason.like("%[bulk]%"),
            )
        ).scalar_one_or_none()
        if dup:
            continue

        discount_amount = (original * Decimal(pct_off) / 100).quantize(Decimal("0.01"))
        proposed = original - discount_amount

        audit: list[dict[str, Any]] = [
            {
                "time": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
                "actor": f"user_id={applicant_uid}",
                "action": f"发起减免申请（{pct_off}%）",
            }
        ]
        approved_at = None
        approved_by = None
        if status in ("approved", "executed"):
            approved_at = now - timedelta(days=3)
            approved_by = approver_uid
            audit.append({
                "time": approved_at.strftime("%Y-%m-%d %H:%M:%S"),
                "actor": "supervisor/admin",
                "action": "批准（bulk seed）",
            })
        if status == "rejected" and rejected_reason:
            audit.append({
                "time": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "actor": "supervisor/admin",
                "action": f"驳回：{rejected_reason}",
            })

        offer = DiscountOffer(
            tenant_id=tenant.id,
            case_id=case_id,
            provider_id=provider_id,
            applicant_user_id=applicant_uid,
            applicant_role=applicant_role,
            offer_type=offer_type,
            original_amount=original,
            proposed_amount=proposed,
            discount_pct=pct_off,
            installment_months=installment_months,
            reason=reason,
            status=status,
            approver_role_required=approver_role,
            approved_by_user_id=approved_by if status in ("approved", "executed") else None,
            approved_at=approved_at,
            rejected_reason=rejected_reason if status == "rejected" else None,
            expires_at=now + timedelta(days=7),
            audit_trail=audit,
        )
        db.add(offer)
        inserted += 1

    db.flush()
    print(f"  [ok] discount_offer 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# legal_conversion_request — 补到约 12 条
# ────────────────────────────────────────────────

BULK_LCR_DATA = [
    # (case_id, requester_user_id, requester_role, status, reviewer_user_id, reviewer_role, reason)
    (34, 5,  "agent",      "pending",   None, None,         "业主多次拒接，欠费超 8 个月，建议转法务。[bulk]"),
    (35, 5,  "agent",      "pending",   None, None,         "业主有服务质量异议且金额较大，催收多次无果。[bulk]"),
    (36, 4,  "supervisor", "approved",  7,    "supervisor", "已核实业主拒不配合，转律师函处理。[bulk]"),
    (37, 12, "agent",      "approved",  13,   "supervisor", "服务商催收员申请转法务，督导审核通过。[bulk]"),
    (38, 5,  "agent",      "rejected",  4,    "supervisor", "欠费金额较小，先电话跟进，暂不转法务。[bulk]"),
    (39, 12, "agent",      "pending",   None, None,         "服务商跟进，业主明确拒绝还款，建议法务介入。[bulk]"),
    (40, 13, "supervisor", "approved",  7,    "supervisor", "长期欠费业主，内部法务已介入。[bulk]"),
    (41, 5,  "agent",      "cancelled", None, None,         "业主已主动联系缴费，撤销转法务申请。[bulk]"),
    (42, 4,  "supervisor", "pending",   None, None,         "超大额欠费（>2.5万），走法务性价比高。[bulk]"),
    (43, 5,  "agent",      "approved",  7,    "supervisor", "反复协商无果，法务函威慑效果更好。[bulk]"),
    (44, 12, "agent",      "rejected",  13,   "supervisor", "案件正在协商减免中，不宜同步转法务。[bulk]"),
    (45, 5,  "agent",      "pending",   None, None,         "业主外地务工，联系不上，转法务挂号函。[bulk]"),
]


def seed_legal_conversion_requests(db, tenant: Tenant, supervisor_user: UserAccount) -> tuple[int, list[int]]:
    """返回 (新增数, 新增的 request_id 列表)"""
    inserted = 0
    new_ids: list[int] = []
    existing_bulk = _count_filtered(db, "legal_conversion_request", "reason", "[bulk]")
    if existing_bulk > 0:
        # 返回已有 bulk 行的 id
        rows = db.execute(
            text("SELECT id FROM legal_conversion_request WHERE reason LIKE '%[bulk]%' ORDER BY id")
        ).scalars().all()
        print(f"  [skip] legal_conversion_request 已有 {existing_bulk} 条 [bulk] 数据，跳过")
        return 0, list(rows)

    now = datetime.now(timezone.utc)
    for row in BULK_LCR_DATA:
        (case_id, requester_uid, requester_role, status,
         reviewer_uid, reviewer_role, reason) = row

        case_exists = db.execute(
            select(CollectionCase).where(CollectionCase.id == case_id)
        ).scalar_one_or_none()
        if not case_exists:
            print(f"  [skip] case_id={case_id} 不存在，跳过该条 legal_conversion_request")
            continue

        reviewed_at = None
        reviewer_note = None
        if status == "approved":
            reviewed_at = now - timedelta(days=2)
            reviewer_note = "已核实，同意转法务处理。"
        elif status == "rejected":
            reviewed_at = now - timedelta(days=1)
            reviewer_note = "暂不符合转法务条件，继续催收。"

        req = LegalConversionRequest(
            tenant_id=tenant.id,
            case_id=case_id,
            requester_user_id=requester_uid,
            requester_role=requester_role,
            reason=reason,
            status=status,
            reviewer_user_id=reviewer_uid,
            reviewer_role=reviewer_role,
            reviewed_at=reviewed_at,
            reviewer_note=reviewer_note,
            related_order_id=None,
        )
        db.add(req)
        db.flush()
        new_ids.append(req.id)
        inserted += 1

    db.flush()
    print(f"  [ok] legal_conversion_request 新增 {inserted} 条")
    return inserted, new_ids


# ────────────────────────────────────────────────
# legal_conversion_request_material — 给若干请求挂附件
# ────────────────────────────────────────────────

def seed_legal_conversion_materials(db, tenant: Tenant, request_ids: list[int], uploader_user_id: int) -> int:
    if not request_ids:
        print("  [skip] 没有可挂附件的 request_id，跳过 material")
        return 0

    existing_bulk = _count_filtered(db, "legal_conversion_request_material", "object_key", "bulk/")
    if existing_bulk > 0:
        print(f"  [skip] legal_conversion_request_material 已有 {existing_bulk} 条 bulk 数据，跳过")
        return 0

    MATERIAL_TEMPLATES = [
        ("欠费明细表.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 48200),
        ("催收记录截图.png",   "image/png",                                                         312400),
        ("业主身份证扫描件.pdf", "application/pdf",                                                 205800),
        ("通话录音摘要.pdf",   "application/pdf",                                                   98600),
        ("物业合同副本.pdf",   "application/pdf",                                                   412000),
        ("欠费通知函回执.jpg",  "image/jpeg",                                                        87200),
    ]

    inserted = 0
    for i, req_id in enumerate(request_ids[:8]):  # 只给前 8 个请求各挂 1-2 附件
        count = 1 if i % 3 == 2 else 2  # 每 3 个里有一个只挂 1 个附件
        for j in range(count):
            tmpl = MATERIAL_TEMPLATES[(i * 2 + j) % len(MATERIAL_TEMPLATES)]
            filename, content_type, size_bytes = tmpl
            mat = LegalConversionRequestMaterial(
                request_id=req_id,
                tenant_id=tenant.id,
                object_key=f"bulk/lcr_material/req_{req_id}_{j}_{filename}",
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                uploaded_by=uploader_user_id,
            )
            db.add(mat)
            inserted += 1

    db.flush()
    print(f"  [ok] legal_conversion_request_material 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# recording_file — 给 call_record 挂录音（直接用原生 SQL，因无 ORM 模型）
# ────────────────────────────────────────────────

def seed_recording_files(db) -> int:
    existing_bulk = _count_filtered(db, "recording_file", "object_key", "bulk/")
    if existing_bulk > 0:
        print(f"  [skip] recording_file 已有 {existing_bulk} 条 bulk 数据，跳过")
        return 0

    # call_log 是旧 PoC 表，call_log_id 可为 NULL（列可空）
    # 我们用 object_key 标识录音文件，不绑 call_log_id（无旧 call_log 行）
    FORMATS = ["mp3", "wav", "m4a", "ogg"]
    DURATIONS = [60, 90, 120, 180, 240, 300, 45, 75]
    SIZES = [512000, 768000, 1024000, 1536000, 2048000, 320000, 640000, 480000]

    # 取 call_record 行（最多 20 条），为每条建一个录音文件
    call_records = db.execute(
        text("SELECT id, case_id, caller_user_id, started_at, duration_sec FROM call_record ORDER BY id LIMIT 20")
    ).fetchall()

    inserted = 0
    now = datetime.now(timezone.utc)
    for i, cr in enumerate(call_records):
        cr_id, case_id, caller_uid, started_at, duration_sec = cr
        fmt = FORMATS[i % len(FORMATS)]
        dur = duration_sec if duration_sec else DURATIONS[i % len(DURATIONS)]
        size = SIZES[i % len(SIZES)]
        obj_key = f"bulk/recordings/call_record_{cr_id}.{fmt}"

        db.execute(
            text("""
                INSERT INTO recording_file
                    (call_log_id, object_key, public_url, src_path, size_bytes, duration_sec, format, match_method, created_at)
                VALUES
                    (NULL, :obj_key, :url, :src_path, :size, :dur, :fmt, 'linked', :created_at)
            """),
            {
                "obj_key": obj_key,
                "url": f"https://minio.internal/autoluyin/{obj_key}",
                "src_path": f"/recordings/{obj_key}",
                "size": size,
                "dur": dur,
                "fmt": fmt,
                "created_at": started_at or now - timedelta(hours=i),
            },
        )
        inserted += 1

    print(f"  [ok] recording_file 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# collection_promise — 补约 15 条（直接 SQL，PoC legacy 表）
# ────────────────────────────────────────────────

def seed_collection_promises(db) -> int:
    existing_bulk = _count_filtered(db, "collection_promise", "note", "[bulk]")
    if existing_bulk > 0:
        print(f"  [skip] collection_promise 已有 {existing_bulk} 条 [bulk] 数据，跳过")
        return 0

    # owner 表有 3 条（id=1,2,3）；owner_id 可为 NULL
    PROMISE_DATA = [
        # (owner_id, amount, promise_date, status, excuse_category, note)
        (1, Decimal("3200.00"), date(2026, 5, 30), "open",      "经济困难", "业主承诺月底前缴清，已录入系统。[bulk]"),
        (1, Decimal("1200.00"), date(2026, 4, 15), "overdue",   "经济困难", "首期还款逾期，业主未联系。[bulk]"),
        (2, Decimal("5600.00"), date(2026, 6, 15), "open",      "服务质量异议", "业主要求先解决投诉再缴费，承诺 6/15 前缴清。[bulk]"),
        (2, Decimal("2000.00"), date(2026, 3, 31), "paid",      "服务质量异议", "业主已按约履行，部分缴清。[bulk]"),
        (3, Decimal("1800.00"), date(2026, 5, 20), "open",      "其他", "业主在外地，承诺返沪后当天缴清。[bulk]"),
        (3, Decimal("1800.00"), date(2026, 2, 28), "overdue",   "其他", "逾期未履约，已转督导跟进。[bulk]"),
        (None, Decimal("8420.00"), date(2026, 6, 30), "open",   "经济困难", "长期欠费业主承诺分批还款，首期 2026-6-30。[bulk]"),
        (None, Decimal("4200.00"), date(2026, 5, 31), "open",   "房屋空置", "业主表示房子出租中，租客代缴款项。[bulk]"),
        (None, Decimal("12600.00"), date(2026, 7, 15), "open",  "服务质量异议", "大额欠费，业主承诺投诉处理后缴清。[bulk]"),
        (None, Decimal("2520.00"), date(2026, 4, 30), "paid",   "其他", "业主已全额缴清，标记 paid。[bulk]"),
        (None, Decimal("9100.00"), date(2026, 5, 15), "overdue","经济困难", "承诺日已过，业主失联，标记逾期。[bulk]"),
        (None, Decimal("6300.00"), date(2026, 6, 20), "open",   "其他", "业主请亲属代联，承诺 6/20 缴。[bulk]"),
        (None, Decimal("3360.00"), date(2026, 5, 10), "cancelled","房屋空置","承诺因业主换了中介而取消，重新谈判。[bulk]"),
        (None, Decimal("21000.00"), date(2026, 8, 1), "open",   "经济困难", "超大额案件，业主承诺 8 月初一次性缴清。[bulk]"),
        (None, Decimal("4500.00"), date(2026, 6, 5), "open",    "其他", "业主出差归来后承诺立即缴款。[bulk]"),
    ]

    inserted = 0
    now = datetime.now(timezone.utc)
    for i, (owner_id, amount, promise_date, status, excuse_cat, note) in enumerate(PROMISE_DATA):
        db.execute(
            text("""
                INSERT INTO collection_promise
                    (owner_id, amount, promise_date, status, excuse_category, evidence_call_id, note, created_at)
                VALUES
                    (:owner_id, :amount, :promise_date, :status, :excuse_cat, NULL, :note, :created_at)
            """),
            {
                "owner_id": owner_id,
                "amount": float(amount),
                "promise_date": promise_date,
                "status": status,
                "excuse_cat": excuse_cat,
                "note": note,
                "created_at": now - timedelta(days=30 - i * 2),
            },
        )
        inserted += 1

    print(f"  [ok] collection_promise 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# notification — 补约 12 条
# ────────────────────────────────────────────────

def seed_notifications(db, tenant: Tenant) -> int:
    existing_bulk = _count_filtered(db, "notification", "body", "[bulk]")
    if existing_bulk > 0:
        print(f"  [skip] notification 已有 {existing_bulk} 条 [bulk] 数据，跳过")
        return 0

    now = datetime.now(timezone.utc)
    NOTIF_DATA = [
        # (user_id, event_type, severity, title, body, read_at)
        (4,  "discount_offer.pending_supervisor",  "warn",     "新减免申请待审批",        "案件 #34 有一条 20% 减免申请，请及时审批。[bulk]", None),
        (4,  "discount_offer.pending_supervisor",  "warn",     "新减免申请待审批",        "案件 #35 有一条 25% 本金折扣申请，金额较大，请谨慎审核。[bulk]", None),
        (3,  "discount_offer.pending_admin",       "warn",     "减免申请待管理员审批",    "案件 #6 有一条 30% 大额减免申请升至管理员，请处理。[bulk]", None),
        (5,  "discount_offer.approved",            "info",     "减免申请已批准",          "您为案件 #7 提交的分期申请已获批准，请告知业主。[bulk]", now - timedelta(hours=2)),
        (5,  "discount_offer.rejected",            "warn",     "减免申请被驳回",          "案件 #9 减免申请被驳回，原因：理由不充分。请重新跟进。[bulk]", None),
        (4,  "legal_conversion_request.pending",   "info",     "新法务转化申请待审批",    "案件 #34 业主欠费 8 个月，催收员建议转法务，请审批。[bulk]", None),
        (4,  "legal_conversion_request.pending",   "info",     "新法务转化申请待审批",    "案件 #35 大额欠费，转法务申请待您审核。[bulk]", None),
        (5,  "legal_conversion_request.approved",  "info",     "法务转化申请已通过",      "您提交的案件 #36 法务转化申请已获批准，法务部门将介入处理。[bulk]", now - timedelta(hours=5)),
        (12, "legal_conversion_request.rejected",  "warn",     "法务转化申请被驳回",      "案件 #38 的法务转化申请被驳回，督导建议继续电话跟进。[bulk]", None),
        (4,  "case.promise_expiring",              "critical", "还款承诺即将到期",        "业主李四（案件 #2）还款承诺将在 3 天后到期，请提前提醒。[bulk]", None),
        (4,  "case.promise_overdue",               "critical", "还款承诺已逾期",          "业主张三（案件 #1）还款承诺已逾期 3 天，请立即跟进。[bulk]", None),
        (3,  "settlement.new_statement",           "info",     "新结算账单已生成",        "2026 年 4 月与 Demo 法务公司的结算账单（共 ¥8,800）已生成，请核对。[bulk]", now - timedelta(days=1)),
    ]

    inserted = 0
    for i, (user_id, event_type, severity, title, body, read_at) in enumerate(NOTIF_DATA):
        notif = Notification(
            tenant_id=tenant.id,
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            title=title,
            body=body,
            payload={"bulk_seed": True, "index": i},
            read_at=read_at,
            created_at=now - timedelta(hours=len(NOTIF_DATA) - i),
        )
        db.add(notif)
        inserted += 1

    db.flush()
    print(f"  [ok] notification 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# qc_alert — 补约 8 条（直接 SQL，PoC legacy 表）
# ────────────────────────────────────────────────

def seed_qc_alerts(db) -> int:
    existing_bulk = _count_filtered(db, "qc_alert", "detail", "[bulk]")
    if existing_bulk > 0:
        print(f"  [skip] qc_alert 已有 {existing_bulk} 条 [bulk] 数据，跳过")
        return 0

    # call_log_id 可为 NULL
    QC_DATA = [
        # (rule, severity, detail, handled)
        ("禁止威胁语言", "critical", "催收员使用了「不缴费就起诉」措辞，触发质检红线。[bulk]",    True),
        ("禁止泄露业主信息", "critical", "通话中催收员提及业主身份证号码后四位，违规。[bulk]",   False),
        ("催收频次超限",    "warn",     "同一业主本月已被外呼 5 次，超过 3 次/月上限。[bulk]",   False),
        ("情绪语气过激",    "warn",     "系统检测到催收员语气激动（情绪评分 0.82），建议复听。[bulk]", True),
        ("承诺录入缺失",    "warn",     "通话结束后 30 分钟内未录入业主还款承诺，请补录。[bulk]", True),
        ("录音时长异常",    "warn",     "通话 5 分钟但录音文件仅 12 秒，疑似录音中断或截断。[bulk]", False),
        ("夜间外呼违规",    "critical", "22:15 对业主发起外呼，违反晚 22:00 禁呼规定。[bulk]",   False),
        ("话术偏差",        "warn",     "催收员未按标准话术开头问候，需补充合规引导语。[bulk]",   True),
    ]

    inserted = 0
    now = datetime.now(timezone.utc)
    for i, (rule, severity, detail, handled) in enumerate(QC_DATA):
        db.execute(
            text("""
                INSERT INTO qc_alert (call_log_id, rule, severity, detail, handled, created_at)
                VALUES (NULL, :rule, :severity, :detail, :handled, :created_at)
            """),
            {
                "rule": rule,
                "severity": severity,
                "detail": detail,
                "handled": handled,
                "created_at": now - timedelta(hours=i * 3),
            },
        )
        inserted += 1

    print(f"  [ok] qc_alert 新增 {inserted} 条")
    return inserted


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("seed_demo_bulk.py — 批量补充模拟数据")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Before 行数
        tables = [
            "discount_offer", "legal_conversion_request",
            "legal_conversion_request_material", "recording_file",
            "collection_promise", "notification", "qc_alert",
        ]
        print("\n[Before] 各表行数:")
        before: dict[str, int] = {}
        for t in tables:
            before[t] = _count(db, t)
            print(f"  {t} = {before[t]}")

        # 查基础引用数据
        tenant = db.execute(select(Tenant).order_by(Tenant.id)).scalars().first()
        if tenant is None:
            print("ERROR: 找不到 Tenant，请先跑 seed_demo.py", file=sys.stderr)
            sys.exit(1)
        print(f"\n[info] 使用 tenant_id={tenant.id} ({tenant.name})")

        supervisor_user = db.execute(
            select(UserAccount).where(UserAccount.id == 4)
        ).scalar_one_or_none()
        admin_user = db.execute(
            select(UserAccount).where(UserAccount.id == 3)
        ).scalar_one_or_none()
        agent_user = db.execute(
            select(UserAccount).where(UserAccount.id == 5)
        ).scalar_one_or_none()

        print("\n[1/7] 补充 discount_offer ...")
        seed_discount_offers(db, tenant, supervisor_user, admin_user)

        print("\n[2/7] 补充 legal_conversion_request ...")
        lcr_count, new_lcr_ids = seed_legal_conversion_requests(db, tenant, supervisor_user)

        # 如果没有新建，就查已有 bulk 行的 id 用于挂附件
        if lcr_count == 0:
            existing_ids = db.execute(
                text("SELECT id FROM legal_conversion_request WHERE reason LIKE '%[bulk]%' ORDER BY id")
            ).scalars().all()
            new_lcr_ids = list(existing_ids)

        print("\n[3/7] 补充 legal_conversion_request_material ...")
        seed_legal_conversion_materials(db, tenant, new_lcr_ids, uploader_user_id=agent_user.id if agent_user else 5)

        print("\n[4/7] 补充 recording_file ...")
        seed_recording_files(db)

        print("\n[5/7] 补充 collection_promise ...")
        seed_collection_promises(db)

        print("\n[6/7] 补充 notification ...")
        seed_notifications(db, tenant)

        print("\n[7/7] 补充 qc_alert ...")
        seed_qc_alerts(db)

        db.commit()

        # After 行数
        print("\n[After] 各表行数:")
        for t in tables:
            after = _count(db, t)
            diff = after - before[t]
            print(f"  {t}: {before[t]} → {after}  (+{diff})")

        # discount_offer 来源分布
        prop_count = db.execute(
            text("SELECT count(*) FROM discount_offer WHERE provider_id IS NULL")
        ).scalar()
        prov_count = db.execute(
            text("SELECT count(*) FROM discount_offer WHERE provider_id IS NOT NULL")
        ).scalar()
        print(f"\n[discount_offer 来源分布]")
        print(f"  物业内勤（provider_id=NULL）: {prop_count}")
        print(f"  服务商（provider_id IS NOT NULL）: {prov_count}")

        print("\n" + "=" * 60)
        print("seed_demo_bulk.py — 完成 ✅")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
