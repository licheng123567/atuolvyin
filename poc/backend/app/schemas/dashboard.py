from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TodayStats(BaseModel):
    outbound_count: int          # 今日总外呼数（CallRecord.started_at 在今天）
    connected_count: int         # 今日接通数（duration_sec > 10 视为接通）
    promised_count: int          # 今日承诺数（AnalysisResult.key_segments['intent'] 含 promise）
    recovered_amount: float      # 今日承诺缴金额合计（promise_made 通话所属 case 的 amount_owed 累计；MVP 无独立回款流水表）


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
    month_promised: int          # 当月该坐席通话中 AI 判定为 promise 的通话数


class AdminDashboardStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    today: TodayStats
    minute_quota: QuotaStats
    public_pool_count: int
    risk_alert_count_7d: int
    top_agents: list[AgentRanking]          # top 10 by today_calls
    script_adoption_trend: list[float]      # 近 7 日每日采用率 [0.5, 0.6, ...]


class ProjectKpi(BaseModel):
    """单项目 KPI（v1.4 — admin 按项目分维度看数据）"""
    project_id: int
    project_name: str
    provider_id: int | None
    provider_name: str | None
    case_count: int
    receivable: float                  # 应收 = 案件 amount_owed 总和
    received: float                    # 已收 = stage='paid' 案件 amount_owed 总和
    recovery_rate: float               # 已收 / 应收
    promised_count: int                # stage='promised' 案件数
    in_progress_count: int             # stage='in_progress' 案件数
    new_count: int                     # stage='new' 案件数
    escalated_count: int               # stage='escalated' 案件数
    closed_count: int                  # stage='paid' OR 'closed' 案件数
    connected_30d: int                 # 近 30 天本项目案件下接通数
    total_calls_30d: int               # 近 30 天本项目案件下总外呼数
