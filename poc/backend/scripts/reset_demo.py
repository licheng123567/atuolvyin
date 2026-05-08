"""reset_demo.py — Demo 数据完全清空 + 重新 seed.

⚠️ 仅限本地 dev 环境使用。
会 TRUNCATE 所有业务表（保留 alembic_version），然后重跑 seed_demo / seed_demo_extra / seed_demo_v14。

用法：
    DATABASE_URL='postgresql+psycopg://autoluyin:autoluyin_dev@localhost:25432/autoluyin' \\
    python -m scripts.reset_demo
"""
from __future__ import annotations

import sys

from app.core.db import SessionLocal
from sqlalchemy import text

# 数据表（除 alembic_version）— TRUNCATE ... CASCADE 一次清空
TABLES = [
    "active_session",
    "analysis_result",
    "audit_log",
    "blockchain_attestation",
    "blockchain_config",
    "call_record",
    "collection_case",
    "customer_followup",
    "dial_token",
    "dispute_record",
    "law_firm",
    "law_firm_lawyer",
    "legal_case",
    "legal_conversion_order",
    "legal_document",
    "legal_document_render",
    "legal_document_template",
    "legal_platform_invoice",
    "legal_service_package",
    "llm_prompt_template",
    "login_otp",
    "notification",
    "notification_delivery_log",
    "owner_profile",
    "plan_config",
    "platform_ops_assignment",
    "project",
    "project_member",
    "provider_tenant_contract",
    "risk_event",
    "risk_keyword",
    "script_template",
    "script_template_version",
    "service_provider",
    "settlement_statement",
    "suggestion_feedback",
    "system_announcement",
    "tenant",
    "tenant_minute_usage",
    "tenant_settings",
    "tenant_suggestion_config",
    "transcript",
    "user_account",
    "user_tenant_membership",
    "work_order",
]


def truncate_all() -> None:
    db = SessionLocal()
    try:
        sql = "TRUNCATE TABLE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE;"
        print(f"[reset] {sql[:80]} ...")
        db.execute(text(sql))
        db.commit()
        print("[reset] 全部业务表已清空 ✅")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


def main() -> None:
    print("=" * 60)
    print("reset_demo.py — Demo 数据清空 + 重 seed")
    print("=" * 60)

    truncate_all()

    # 重新跑 3 个 seed 脚本（顺序依赖）
    print("\n--- step 1/3: seed_demo ---")
    from scripts import seed_demo
    seed_demo.main()

    print("\n--- step 2/3: seed_demo_extra ---")
    from scripts import seed_demo_extra
    seed_demo_extra.main()

    print("\n--- step 3/3: seed_demo_v14 ---")
    from scripts import seed_demo_v14
    seed_demo_v14.main()

    print("\n" + "=" * 60)
    print("reset_demo.py — 全部完成 ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
