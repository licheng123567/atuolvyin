// v2.0 Task 3 — Screen 1：催收员工作台首页（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-home
// 数据源：
//   GET /api/v1/agent/me/today-kpi    — summary card 三列
//   GET /api/v1/agent/me/performance  — 本月通话分钟卡 + 配额
//   GET /api/v1/agent/cases           — 最近跟进案件（前 3 条）
import { useState } from "react";
import { useCustom, useGetIdentity, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import type { AuthUser } from "../../../providers/auth-provider";
import { Bridge, type CapabilityState } from "../../../lib/jsBridge";
import { stageBadgeClass, stageLabel } from "../../../lib/caseStage";

/**
 * v2.1 Task 6 — 顶部录音能力 banner
 * - realtime: 绿色，可关闭（不打扰已就绪用户）
 * - post_upload: 橙色，不可关闭（提醒事后上传模式）
 * - incompatible: 红色，不可关闭（强提示风险）
 * - unknown: 不展示（避免冷启动时干扰）
 */
function CapabilityBanner() {
  const [dismissed, setDismissed] = useState(false);
  const state: CapabilityState = Bridge.getCapability();

  if (state.capability === "unknown") return null;
  if (state.capability === "realtime" && dismissed) return null;

  const variant =
    state.capability === "realtime"
      ? "green"
      : state.capability === "post_upload"
        ? "orange"
        : "red";

  const text =
    state.capability === "realtime"
      ? `🟢 实时通话分析已就绪 — ${state.rom}`
      : state.capability === "post_upload"
        ? `🟡 事后上传模式 — ${state.rom}`
        : `🔴 录音不可用 — ${state.rom}`;

  const showClose = state.capability === "realtime";

  return (
    <div className={`cap-banner cap-banner-${variant}`}>
      <span>{text}</span>
      {state.capability !== "realtime" && (
        <a href="/app/profile" className="cap-banner-link">
          详情
        </a>
      )}
      {showClose && (
        <button
          type="button"
          className="cap-banner-close"
          onClick={() => setDismissed(true)}
          aria-label="关闭提示"
        >
          ×
        </button>
      )}
    </div>
  );
}

// Backend schema mirror（手抄自 poc/backend/app/api/agent_me.py / agent_cases.py）
interface TodayKpi {
  date: string;
  calls_today: number;
  calls_target: number;
  connected_today: number;
  promised_today: number;
  paid_today: number;
  minutes_used_today: number;
}

interface AgentPerformance {
  user_id: number;
  name: string;
  year_month: string;
  month_calls: number;
  month_connected: number;
  month_promised_cases: number;
  month_paid_cases: number;
  month_paid_amount: string;
  conversion_rate: number | null;
  minutes_used: number;
  minutes_quota: number | null;
  rank_in_tenant: number;
}

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
}

function formatGreetingDate(d: Date): string {
  const weekday = new Intl.DateTimeFormat("zh-CN", { weekday: "long" }).format(d);
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekday}`;
}

function timeOfDayGreeting(d: Date): string {
  const h = d.getHours();
  if (h < 11) return "早上好";
  if (h < 13) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

function formatYuan(value: string | null | undefined): string {
  if (!value) return "¥0";
  const n = Number(value);
  if (!Number.isFinite(n)) return `¥${value}`;
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

export function MobileHomePage() {
  const navigate = useNavigate();
  const { data: identity } = useGetIdentity<AuthUser>();
  const userName = identity?.name ?? "";
  const now = new Date();

  const { query: kpiQ } = useCustom<TodayKpi>({
    url: "agent/me/today-kpi",
    method: "get",
  });
  const { query: perfQ } = useCustom<AgentPerformance>({
    url: "agent/me/performance",
    method: "get",
  });
  const { query: casesQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 3 },
  });

  const kpi = kpiQ.data?.data;
  const perf = perfQ.data?.data;
  const cases: CaseItem[] = casesQ.data?.data ?? [];

  // "今日待拨" backend 没直接提供；用 calls_target - calls_today 作为剩余指标。
  const todayPending = kpi
    ? Math.max(kpi.calls_target - kpi.calls_today, 0)
    : 0;
  const todayCalled = kpi?.calls_today ?? 0;
  const todayPromised = kpi?.promised_today ?? 0;

  const minutesUsed = perf?.minutes_used ?? 0;
  const minutesQuota = perf?.minutes_quota ?? 0;
  const minutesRemaining = Math.max(minutesQuota - minutesUsed, 0);
  const minutesPct =
    minutesQuota > 0
      ? Math.min(100, (minutesUsed / minutesQuota) * 100)
      : 0;

  const handleStartDial = () => {
    // Task 5 之前先在 WebView 内部跳到案件列表
    navigate("/app/cases");
  };

  const handleOpenCase = (id: number) => {
    if (Bridge.isAndroid()) {
      Bridge.openCaseDetail(id);
    } else {
      navigate(`/app/cases/${id}`);
    }
  };

  return (
    <div>
      {/* ── v2.1 — 顶部录音能力 banner ── */}
      <CapabilityBanner />

      {/* ── 顶部 greeting ── */}
      <div className="app-header">
        <div className="greeting">
          {timeOfDayGreeting(now)}，{userName} 👋
        </div>
        <div className="greeting-date">{formatGreetingDate(now)}</div>
      </div>

      {/* ── Summary card ── */}
      <div className="summary-card">
        <div className="summary-card-title">今日外呼任务</div>
        <div className="summary-stats">
          <div className="summary-stat">
            <div className="summary-stat-value">{todayPending}</div>
            <div className="summary-stat-label">今日待拨</div>
          </div>
          <div className="summary-stat">
            <div className="summary-stat-value">{todayCalled}</div>
            <div className="summary-stat-label">已拨</div>
          </div>
          <div className="summary-stat">
            <div className="summary-stat-value">{todayPromised}</div>
            <div className="summary-stat-label">承诺缴费</div>
          </div>
        </div>
      </div>

      {/* ── 本月通话分钟 ── */}
      <div className="minute-quota-card">
        <div className="minute-quota-row">
          <span className="minute-quota-title">本月通话分钟</span>
          <span className="minute-quota-meta">
            配额 {minutesQuota.toLocaleString("zh-CN")} 分
          </span>
        </div>
        <div className="minute-quota-numrow">
          <span className="minute-quota-value">{minutesUsed}</span>
          <span className="minute-quota-unit">分钟已用</span>
          <span className="minute-quota-remaining">
            剩余 {minutesRemaining}
          </span>
        </div>
        <div className="minute-quota-bar-bg">
          <div
            className="minute-quota-bar-fg"
            style={{ width: `${minutesPct.toFixed(1)}%` }}
          />
        </div>
      </div>

      {/* ── 大蓝色按钮 ── */}
      <button type="button" className="big-btn" onClick={handleStartDial}>
        📞 立即开始外呼
      </button>

      {/* ── 拨打请求卡（TODO Task 5+：接 dial-request 列表 endpoint） ── */}
      <div className="request-card">
        <div className="request-card-top">
          <Bell
            size={16}
            strokeWidth={1.75}
            color="#D97706"
            style={{ verticalAlign: "middle" }}
          />
          <span>主管发来拨打请求</span>
        </div>
        <div className="request-card-body">
          <div className="request-card-name">张建国 · 3栋2单元1201</div>
          <div className="request-card-amount">¥3,200</div>
          <div style={{ fontSize: 12, color: "#6b7280" }}>
            欠缴8个月 · 王主管指派
          </div>
          <div className="request-card-actions">
            <button type="button" className="btn-call-now">
              立即拨打
            </button>
            <button type="button" className="btn-call-later">
              稍后处理
            </button>
          </div>
        </div>
      </div>

      {/* ── 最近跟进案件 ── */}
      <div className="app-section">
        <div className="app-section-title">最近跟进案件</div>
        {cases.length === 0 && (
          <div
            style={{
              background: "white",
              padding: 16,
              borderRadius: 10,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            暂无跟进中的案件
          </div>
        )}
        {cases.map((c) => (
          <div
            key={c.id}
            className="case-list-item"
            onClick={() => handleOpenCase(c.id)}
          >
            <div>
              <div className="case-list-name">{c.owner.name}</div>
              <div className="case-list-sub">
                {c.owner.building ?? ""}
                {c.owner.room ? ` ${c.owner.room}` : ""}
                {c.months_overdue ? ` · 欠缴${c.months_overdue}个月` : ""}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="case-list-amount">{formatYuan(c.amount_owed)}</div>
              <span className={stageBadgeClass(c.stage)} style={{ fontSize: 11 }}>
                {stageLabel(c.stage)}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div style={{ height: 16 }} />
    </div>
  );
}

export default MobileHomePage;
