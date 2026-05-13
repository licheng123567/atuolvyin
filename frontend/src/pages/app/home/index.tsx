// v2.0 Task 3 — Screen 1：催收员工作台首页（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-home
// 数据源：
//   GET /api/v1/agent/me/today-kpi    — summary card 三列
//   GET /api/v1/agent/me/performance  — 本月通话分钟卡 + 配额
//   GET /api/v1/agent/cases?today=true — 今日待拨案件列表 (Top 5)
//
// v2.2 Module B 改造：
//   B1 — CapabilityBanner 默认收为顶部小圆点；点击展开 BottomSheet。
//        incompatible 例外：保留红色 banner（合规强提示）。
//   B2 — Summary card 下方新增「今日待拨案件」Top 5 列表，点击直接拨号。
//   B3 — header 右侧新增搜索快捷入口，跳 cases 页并自动 focus。
import { useState } from "react";
import { useCustom, useGetIdentity, useList } from "@refinedev/core";
import { useNavigate } from "react-router-dom";
import { Bell, Search } from "lucide-react";
import type { AuthUser } from "../../../providers/auth-provider";
import { Bridge, type CapabilityState } from "../../../lib/jsBridge";
import { stageBadgeClass, stageLabel } from "../../../lib/caseStage";

/**
 * v2.2 Module B1 — 顶部录音能力指示器
 * 设计变更：把 v2.1 的常驻 banner 收成右上角小圆点 + BottomSheet。
 * - realtime (绿) / post_upload (橙)：仅显示圆点，点击展开 BottomSheet 看详情
 * - incompatible (红)：仍保留 v2.1 的红色 banner（合规强提示，不可收纳）
 * - unknown：不展示（避免冷启动时干扰）
 */
function CapabilityIndicator({
  state,
  onOpen,
}: {
  state: CapabilityState;
  onOpen: () => void;
}) {
  if (state.capability === "unknown") return null;
  if (state.capability === "incompatible") return null; // 由 IncompatibleBanner 处理

  const variant =
    state.capability === "realtime"
      ? "green"
      : "orange";

  const label =
    state.capability === "realtime"
      ? "实时通话分析已就绪"
      : "事后上传模式";

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`录音能力：${label}`}
      title={label}
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        border: "none",
        background: "transparent",
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 0,
      }}
    >
      <span
        style={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          background: variant === "green" ? "#22c55e" : "#f59e0b",
          boxShadow: `0 0 0 3px ${variant === "green" ? "rgba(34,197,94,0.18)" : "rgba(245,158,11,0.18)"}`,
        }}
      />
    </button>
  );
}

function IncompatibleBanner({ state }: { state: CapabilityState }) {
  if (state.capability !== "incompatible") return null;
  return (
    <div className="cap-banner cap-banner-red">
      <span>🔴 录音不可用 — {state.rom}</span>
      <a href="/app/profile" className="cap-banner-link">
        详情
      </a>
    </div>
  );
}

function formatCheckedAt(ms: number): string {
  if (!ms || ms <= 0) return "尚未检测";
  const d = new Date(ms);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function CapabilityBottomSheet({
  state,
  onClose,
}: {
  state: CapabilityState;
  onClose: () => void;
}) {
  const headline =
    state.capability === "realtime"
      ? "🟢 实时通话分析已就绪"
      : state.capability === "post_upload"
        ? "🟡 事后上传模式"
        : state.capability === "incompatible"
          ? "🔴 录音不可用"
          : "录音能力未检测";
  return (
    <>
      {/* mask */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.4)",
          zIndex: 50,
        }}
      />
      {/* sheet */}
      <div
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          background: "white",
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: "20px 20px 28px",
          zIndex: 51,
          boxShadow: "0 -4px 16px rgba(0,0,0,0.15)",
        }}
      >
        <div
          style={{
            width: 36,
            height: 4,
            borderRadius: 2,
            background: "#e5e7eb",
            margin: "0 auto 16px",
          }}
        />
        <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>
          {headline}
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
          设备机型：{state.rom || "未识别"}
        </div>
        {state.guidance && (
          <div
            style={{
              marginTop: 12,
              fontSize: 13,
              color: "#374151",
              lineHeight: 1.6,
            }}
          >
            {state.guidance}
          </div>
        )}
        <div style={{ marginTop: 12, fontSize: 12, color: "#9ca3af" }}>
          上次检测：{formatCheckedAt(state.checkedAtMs)}
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{
            marginTop: 18,
            width: "100%",
            padding: "12px",
            background: "#1A56DB",
            color: "white",
            border: "none",
            borderRadius: 10,
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          知道了
        </button>
      </div>
    </>
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
  phone?: string | null;
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

  // v2.2 — capability 指示器 & sheet
  const capState: CapabilityState = Bridge.getCapability();
  const [capSheetOpen, setCapSheetOpen] = useState(false);

  const { query: kpiQ } = useCustom<TodayKpi>({
    url: "agent/me/today-kpi",
    method: "get",
  });
  const { query: perfQ } = useCustom<AgentPerformance>({
    url: "agent/me/performance",
    method: "get",
  });
  // v2.2 Module B2 — 今日待拨 Top 5（后端已支持 today=true 过滤）
  const { query: todayCasesQ } = useList<CaseItem>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 5 },
    filters: [{ field: "today", operator: "eq", value: true }],
  });

  const kpi = kpiQ.data?.data;
  const perf = perfQ.data?.data;
  const todayCases: CaseItem[] = todayCasesQ.data?.data ?? [];

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

  // v2.2 Module B2 — 任务列表点击直接拨号
  const handleDialCase = (c: CaseItem) => {
    // incompatible 设备拨号前确认（与 case detail 行为对齐）
    if (capState.capability === "incompatible") {
      const ok = window.confirm(
        `您的设备 (${capState.rom || "未识别"}) 无法保存通话录音，本次通话将无 AI 分析。\n\n是否继续拨号？`,
      );
      if (!ok) return;
    }
    const phone = c.owner.phone ?? c.owner.phone_masked;
    Bridge.dialCase({
      case_id: c.id,
      phone,
      owner_name: c.owner.name,
    });
  };

  // v2.2 Module B3 — header 搜索快捷入口
  const handleOpenSearch = () => {
    navigate("/app/cases?focus=search");
  };

  return (
    <div>
      {/* ── v2.2 B1 — incompatible 强提示保留 banner（合规） ── */}
      <IncompatibleBanner state={capState} />

      {/* ── 顶部 greeting + 右上角 action icons ── */}
      <div
        className="app-header"
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="greeting">
            {timeOfDayGreeting(now)}，{userName} 👋
          </div>
          <div className="greeting-date">{formatGreetingDate(now)}</div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            paddingTop: 4,
          }}
        >
          <button
            type="button"
            onClick={handleOpenSearch}
            aria-label="搜索案件"
            style={{
              width: 36,
              height: 36,
              border: "none",
              background: "#f3f4f6",
              borderRadius: "50%",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#374151",
            }}
          >
            <Search size={18} strokeWidth={2} />
          </button>
          <CapabilityIndicator
            state={capState}
            onOpen={() => setCapSheetOpen(true)}
          />
        </div>
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

      {/* ── v2.2 B2 — 今日待拨案件 Top 5（点击直接拨号） ── */}
      <div className="app-section">
        <div
          className="app-section-title"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>今日待拨案件</span>
          <a
            onClick={() => navigate("/app/cases")}
            style={{
              fontSize: 12,
              color: "#1A56DB",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            查看全部 ›
          </a>
        </div>
        {todayCasesQ.isLoading && (
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
            加载中…
          </div>
        )}
        {!todayCasesQ.isLoading && todayCases.length === 0 && (
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
            今日暂无待拨案件 🎉
          </div>
        )}
        {todayCases.map((c) => (
          <div
            key={c.id}
            className="case-list-item"
            onClick={() => handleDialCase(c)}
            role="button"
            aria-label={`拨打 ${c.owner.name}`}
          >
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="case-list-name">{c.owner.name}</div>
              <div className="case-list-sub">
                {c.owner.building ?? ""}
                {c.owner.room ? ` ${c.owner.room}` : ""}
                {c.months_overdue ? ` · 欠缴${c.months_overdue}个月` : ""}
              </div>
            </div>
            <div
              style={{
                textAlign: "right",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-end",
                gap: 4,
                marginLeft: 8,
              }}
            >
              <div className="case-list-amount">{formatYuan(c.amount_owed)}</div>
              <span className={stageBadgeClass(c.stage)} style={{ fontSize: 11 }}>
                {stageLabel(c.stage)}
              </span>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleOpenCase(c.id);
              }}
              aria-label="查看详情"
              style={{
                marginLeft: 8,
                width: 28,
                height: 28,
                border: "1px solid #e5e7eb",
                background: "white",
                borderRadius: 6,
                color: "#6b7280",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              …
            </button>
          </div>
        ))}
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

      <div style={{ height: 16 }} />

      {/* ── v2.2 B1 — Capability BottomSheet ── */}
      {capSheetOpen && (
        <CapabilityBottomSheet
          state={capState}
          onClose={() => setCapSheetOpen(false)}
        />
      )}
    </div>
  );
}

export default MobileHomePage;
