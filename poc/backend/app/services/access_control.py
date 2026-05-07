"""Sprint 16.4 — Service provider data access control (post-termination window).

D3 — 解约后数据可见性：
  active 合同：直通
  terminated 合同：terminated_at 起 30 天内只读；超过 30 天禁止读
  60 天后由后台 worker 软删历史数据

业主姓名/手机号在合同 terminated 那一刻起对服务商不可见（脱敏）。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.tenant import ProviderTenantContract


READ_ONLY_DAYS = 30
PURGE_AFTER_DAYS = 60


def contract_access_level(contract: ProviderTenantContract) -> str:
    """Return access level: 'rw' / 'readonly' / 'denied'.

    rw       - 合同正常活跃
    readonly - 已 terminated < 30 天（仅可查阅历史）
    denied   - 已 terminated >= 30 天 或 paused（不可读）
    """
    if contract.status == "active":
        return "rw"
    if contract.status == "terminated" and contract.terminated_at:
        delta = datetime.now(UTC) - contract.terminated_at
        if delta < timedelta(days=READ_ONLY_DAYS):
            return "readonly"
        return "denied"
    # paused / 未知 → 拒绝
    return "denied"


def can_provider_see_owner_pii(contract: ProviderTenantContract) -> bool:
    """业主姓名/手机号：仅 active 合同可见；terminated 起立刻脱敏。"""
    return contract.status == "active"


def days_until_readonly_expires(contract: ProviderTenantContract) -> int | None:
    """合同 terminated 后还剩多少天只读。None = 不在只读期。"""
    if contract.status != "terminated" or not contract.terminated_at:
        return None
    delta = (
        contract.terminated_at + timedelta(days=READ_ONLY_DAYS)
    ) - datetime.now(UTC)
    return max(0, delta.days)
