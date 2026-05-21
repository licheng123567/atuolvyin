"""v0.9.0 — N 天未联系自动释放公海。

诱因:用户人工验收 v0.8.0 后,提出「服务商管理员及物业管理员针对多少天没有
联系的业主自动释放到公海」需求。

逻辑:
  1. 遍历所有 tenants:读 TenantSettings.auto_release_stale_days (跳过 0)
     找 case.assigned_to IS NOT NULL + last_contact_at < now - N 天
     + stage IN (new/contacting/promised/escalated) + provider_id IS NULL
     → assigned_to=None + pool_type="public"(物业公海)
  2. 遍历所有 providers:读 ProviderSettings.auto_release_stale_days (跳过 0)
     找 case.assigned_to IS NOT NULL + last_contact_at < now - N 天
     + 该 case 是服务商接案(provider_id == this_provider.id)
     → assigned_to=None + pool_type="public"(进物业 / 服务商内部公海;
       因 case.provider_id 已标记,服务商端筛 provider_id=mine 即可恢复)
  3. 每次释放写 audit_log (action="case.auto_released_stale")
     payload: {scope, n_days, last_contact_at, prev_assigned_to}

触发方式:
  - Celery beat(若运行):每日 02:00 自动跑(配置见 celery_app.beat_schedule)
  - 手动:python -m app.worker.tasks.auto_release_stale
  - 测试:CELERY_TASK_ALWAYS_EAGER=True 让 .delay() 立即执行

注:case.provider_id 字段已存在(服务商承接的案件会有此字段);本任务不区分
「服务商公海 vs 物业公海」的实际表字段 — 而是依赖前端基于 provider_id
过滤决定显示在哪个公海(provider_id=NULL 显示物业公海;非 NULL 显示该服务商公海)。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_session_factory():
    global _engine, _SessionLocal
    if _engine is None:
        url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin",
        )
        _engine = create_engine(url)
        _SessionLocal = sessionmaker(_engine)
    return _SessionLocal


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 仅释放未结案 / 未付清的活跃 stage,避免把已结案案件误释放
RELEASABLE_STAGES = ("new", "contacting", "promised", "escalated")


def _release_one_tenant(db: Session, tenant_id: int, n_days: int) -> int:
    """释放一个物业 tenant 下符合条件的案件,返回释放条数。"""
    from app.models.case import CollectionCase
    from app.services.audit import log_audit

    cutoff = datetime.now(UTC) - timedelta(days=n_days)
    stale_cases = (
        db.execute(
            select(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to.isnot(None))
            .where(CollectionCase.last_contact_at < cutoff)
            .where(CollectionCase.stage.in_(RELEASABLE_STAGES))
            .where(CollectionCase.provider_id.is_(None))  # 仅物业自营(无服务商)
        )
        .scalars()
        .all()
    )

    count = 0
    for case in stale_cases:
        prev_agent = case.assigned_to
        case.assigned_to = None
        case.pool_type = "public"
        log_audit(
            db,
            actor_user_id=None,
            actor_role="system",
            tenant_id=tenant_id,
            action="case.auto_released_stale",
            target_type="case",
            target_id=case.id,
            payload={
                "scope": "tenant",
                "n_days": n_days,
                "last_contact_at": case.last_contact_at.isoformat()
                if case.last_contact_at
                else None,
                "prev_assigned_to": prev_agent,
            },
        )
        count += 1
    return count


def _release_one_provider(db: Session, provider_id: int, n_days: int) -> int:
    """释放一个服务商接的符合条件的案件,返回释放条数。

    服务商内部公海 = 同 provider_id 下 assigned_to=NULL 的案件
    (前端按 provider_id 筛选已实现,见 ProviderPoolPage)。
    """
    from app.models.case import CollectionCase
    from app.services.audit import log_audit

    cutoff = datetime.now(UTC) - timedelta(days=n_days)
    stale_cases = (
        db.execute(
            select(CollectionCase)
            .where(CollectionCase.provider_id == provider_id)
            .where(CollectionCase.assigned_to.isnot(None))
            .where(CollectionCase.last_contact_at < cutoff)
            .where(CollectionCase.stage.in_(RELEASABLE_STAGES))
        )
        .scalars()
        .all()
    )

    count = 0
    for case in stale_cases:
        prev_agent = case.assigned_to
        case.assigned_to = None
        case.pool_type = "public"  # 服务商公海前端按 provider_id 过滤
        log_audit(
            db,
            actor_user_id=None,
            actor_role="system",
            tenant_id=case.tenant_id,
            action="case.auto_released_stale",
            target_type="case",
            target_id=case.id,
            payload={
                "scope": "provider",
                "provider_id": provider_id,
                "n_days": n_days,
                "last_contact_at": case.last_contact_at.isoformat()
                if case.last_contact_at
                else None,
                "prev_assigned_to": prev_agent,
            },
        )
        count += 1
    return count


@celery_app.task(name="tasks.auto_release_stale_cases")
def auto_release_stale_cases() -> dict:
    """每日 02:00 触发(配置见 celery_app.beat_schedule)。

    返回 {tenant_count, provider_count, total_released} 用于监控。
    """
    from app.models.settings import ProviderSettings, TenantSettings

    total_tenant = 0
    total_provider = 0
    tenant_count = 0
    provider_count = 0

    with _get_db() as db:
        # 1) 物业租户
        tenant_settings = (
            db.execute(
                select(TenantSettings).where(TenantSettings.auto_release_stale_days > 0)
            )
            .scalars()
            .all()
        )
        for ts in tenant_settings:
            try:
                released = _release_one_tenant(db, ts.tenant_id, ts.auto_release_stale_days)
                if released > 0:
                    logger.info(
                        "auto_release tenant=%d n_days=%d released=%d",
                        ts.tenant_id, ts.auto_release_stale_days, released,
                    )
                total_tenant += released
                tenant_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("auto_release tenant=%d failed: %s", ts.tenant_id, exc)

        # 2) 服务商
        provider_settings = (
            db.execute(
                select(ProviderSettings).where(ProviderSettings.auto_release_stale_days > 0)
            )
            .scalars()
            .all()
        )
        for ps in provider_settings:
            try:
                released = _release_one_provider(
                    db, ps.provider_id, ps.auto_release_stale_days
                )
                if released > 0:
                    logger.info(
                        "auto_release provider=%d n_days=%d released=%d",
                        ps.provider_id, ps.auto_release_stale_days, released,
                    )
                total_provider += released
                provider_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("auto_release provider=%d failed: %s", ps.provider_id, exc)

    result = {
        "tenant_count": tenant_count,
        "provider_count": provider_count,
        "total_released": total_tenant + total_provider,
        "by_scope": {"tenant": total_tenant, "provider": total_provider},
    }
    logger.info("auto_release_stale_cases done: %s", result)
    return result


if __name__ == "__main__":
    # CLI 入口:python -m app.worker.tasks.auto_release_stale
    logging.basicConfig(level=logging.INFO)
    result = auto_release_stale_cases()
    print(result)
