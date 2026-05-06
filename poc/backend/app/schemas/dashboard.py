from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TodayStats(BaseModel):
    outbound_count: int          # 今日总外呼数（CallRecord.started_at 在今天）
    connected_count: int         # 今日接通数（duration_sec > 10 视为接通）
    promised_count: int          # 今日承诺数（AnalysisResult.key_segments['intent'] 含 promise）
    recovered_amount: float      # 今日回款（MVP 占位 0.0）


class QuotaStats(BaseModel):
    used_min: int                # 总分钟（兼容字段 = realtime + post）
    total_min: int | None
    remaining_min: int | None
    warning: bool                # used >= 80% total
    # Sprint 14.1 — 实时 vs 事后分别（PRD §20.1.1）
    realtime_min: int = 0
    post_min: int = 0
    realtime_quota: int | None = None  # 套餐细分配额，None 表示不分别拦截
    post_quota: int | None = None


class AgentRanking(BaseModel):
    user_id: int
    name: str
    today_calls: int
    month_promised: int          # MVP: 占位 0（等结算 sprint 实现）


class AdminDashboardStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    today: TodayStats
    minute_quota: QuotaStats
    public_pool_count: int
    risk_alert_count_7d: int
    top_agents: list[AgentRanking]          # top 10 by today_calls
    script_adoption_trend: list[float]      # 近 7 日每日采用率 [0.5, 0.6, ...]
