// frontend/src/pages/admin/dashboard/index.tsx
import { useCustom } from "@refinedev/core";
import { Activity, AlertTriangle, Users, TrendingUp, PhoneCall, BadgeCheck, DollarSign } from "lucide-react";
import type { ReactNode } from "react";
import { formatMinutes, getQuotaWarning, formatCurrency } from "./helpers";

interface TodayStats {
  outbound_count: number;
  connected_count: number;
  promised_count: number;
  recovered_amount: number;
}

interface QuotaStats {
  used_min: number;
  total_min: number | null;
  remaining_min: number | null;
  warning: boolean;
}

interface AgentRanking {
  user_id: number;
  name: string;
  today_calls: number;
  month_promised: number;
}

interface DashboardStats {
  today: TodayStats;
  minute_quota: QuotaStats;
  public_pool_count: number;
  risk_alert_count_7d: number;
  top_agents: AgentRanking[];
  script_adoption_trend: number[];
}

export function AdminDashboardPage() {
  const { query } = useCustom<DashboardStats>({
    url: "admin/dashboard/stats",
    method: "get",
  });
  const stats = query.data?.data;

  if (query.isLoading) return <div className="p-6 text-neutral-500">加载中…</div>;
  if (query.isError || !stats) return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;

  // 防御 server response 字段缺失（部分租户 / 新建租户 / 旧 schema 行）
  const today = stats.today ?? {
    outbound_count: 0,
    connected_count: 0,
    promised_count: 0,
    recovered_amount: 0,
  };
  const minuteQuota = stats.minute_quota ?? {
    used_min: 0,
    total_min: 0,
    remaining_min: null,
    warning: false,
  };
  const topAgents = stats.top_agents ?? [];
  const scriptTrend = stats.script_adoption_trend ?? [];
  const quotaState = getQuotaWarning(minuteQuota.used_min, minuteQuota.total_min);

  return (
    <div style={{ padding: 24 }} className="space-y-6">
      {/* 5 KPI 卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16 }}>
        <KpiCard
          label="今日外呼"
          value={today.outbound_count}
          icon={<Activity size={14} />}
        />
        <KpiCard
          label="今日接通"
          value={today.connected_count}
          icon={<PhoneCall size={14} />}
        />
        <KpiCard
          label="今日承诺"
          value={today.promised_count}
          icon={<BadgeCheck size={14} />}
        />
        <KpiCard
          label="今日回款"
          value={formatCurrency(today.recovered_amount)}
          icon={<DollarSign size={14} />}
        />
        <KpiCard
          label="本月分钟用量"
          value={`${formatMinutes(minuteQuota.used_min)} / ${formatMinutes(minuteQuota.total_min)}`}
          warn={quotaState !== "ok"}
          subtext={
            stats.minute_quota?.remaining_min != null
              ? `剩余 ${formatMinutes(stats.minute_quota.remaining_min)} 分钟`
              : undefined
          }
        />
      </div>

      {/* 公海 / 风控告警 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <SmallCard
          label="公海待分配案件"
          value={stats.public_pool_count}
          icon={<Users size={16} />}
        />
        <SmallCard
          label="近7日风控告警"
          value={stats.risk_alert_count_7d}
          icon={<AlertTriangle size={16} />}
          warn={stats.risk_alert_count_7d > 0}
        />
      </div>

      {/* Top10 排名表 */}
      <div style={{ background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }}>
        <h3 style={{ fontWeight: 600, marginBottom: 12, fontSize: 15 }}>全员排名（今日通话量）</h3>
        <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "#6b7280", textAlign: "left" }}>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>排名</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>姓名</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>今日通话</th>
              <th style={{ padding: "8px 10px", fontWeight: 500 }}>本月承诺</th>
            </tr>
          </thead>
          <tbody>
            {topAgents.map((a: AgentRanking, i: number) => (
              <tr key={a.user_id} style={{ borderTop: "1px solid #f3f4f6" }}>
                <td style={{ padding: "8px 10px" }}>
                  <RankBadge rank={i + 1} />
                </td>
                <td style={{ padding: "8px 10px" }}>{a.name}</td>
                <td style={{ padding: "8px 10px" }}>{a.today_calls}</td>
                <td style={{ padding: "8px 10px" }}>{a.month_promised}</td>
              </tr>
            ))}
            {topAgents.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}
                >
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* AI 话术采用率趋势（SVG 折线图）*/}
      <div style={{ background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }}>
        <h3
          style={{
            fontWeight: 600,
            marginBottom: 12,
            fontSize: 15,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <TrendingUp size={16} /> AI 话术采用率（近7日）
        </h3>
        <SimpleLineChart values={scriptTrend} />
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  warn?: boolean;
  subtext?: string;
}

function KpiCard({ label, value, icon, warn = false, subtext }: KpiCardProps) {
  return (
    <div
      style={{
        background: warn ? "#fffbeb" : "#fff",
        borderRadius: 8,
        padding: 16,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        border: warn ? "1px solid #fed7aa" : "1px solid #f3f4f6",
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: warn ? "#92400e" : "#6b7280",
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        {icon}
        {label}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 600,
          marginTop: 6,
          color: warn ? "#d97706" : "#111827",
        }}
      >
        {value}
      </div>
      {subtext && (
        <div style={{ fontSize: 11, color: warn ? "#92400e" : "#9ca3af", marginTop: 4 }}>
          {subtext}
        </div>
      )}
    </div>
  );
}

interface SmallCardProps {
  label: string;
  value: number;
  icon: ReactNode;
  warn?: boolean;
}

function SmallCard({ label, value, icon, warn = false }: SmallCardProps) {
  return (
    <div
      style={{
        background: warn ? "#fff7ed" : "#fff",
        borderRadius: 8,
        padding: 16,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        border: warn ? "1px solid #fed7aa" : "1px solid #f3f4f6",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: warn ? "#92400e" : "#374151",
          fontSize: 14,
        }}
      >
        {icon}
        {label}
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: warn ? "#ea580c" : "#111827",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const medalColors: Record<number, string> = {
    1: "#fbbf24",
    2: "#9ca3af",
    3: "#cd7c2c",
  };
  const bg = medalColors[rank];
  if (bg) {
    return (
      <span
        style={{
          background: bg,
          color: "#fff",
          width: 22,
          height: 22,
          borderRadius: "50%",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 700,
        }}
      >
        {rank}
      </span>
    );
  }
  return <span style={{ color: "#6b7280", paddingLeft: 4 }}>{rank}</span>;
}

function SimpleLineChart({ values }: { values: number[] }) {
  const w = 600;
  const h = 100;
  const pad = 10;
  const len = values.length;

  if (len === 0) {
    return (
      <div style={{ textAlign: "center", color: "#9ca3af", padding: 24, fontSize: 13 }}>
        暂无趋势数据
      </div>
    );
  }

  const maxVal = Math.max(...values, 0.001); // avoid division by zero

  const getX = (i: number) =>
    len === 1
      ? w / 2
      : pad + (i / (len - 1)) * (w - pad * 2);

  const getY = (v: number) =>
    h - pad - (v / maxVal) * (h - pad * 2);

  const points = values
    .map((v, i) => `${getX(i)},${getY(v)}`)
    .join(" ");

  // compute latest rate label
  const latest = values[values.length - 1];
  const latestPct = `${(latest * 100).toFixed(1)}%`;

  return (
    <div>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#1A56DB", marginBottom: 8 }}>
        {latestPct}
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: 80 }}>
        {/* filled area under line */}
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(59,130,246)" stopOpacity={0.15} />
            <stop offset="100%" stopColor="rgb(59,130,246)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <polygon
          points={`${getX(0)},${h - pad} ${points} ${getX(len - 1)},${h - pad}`}
          fill="url(#lineGrad)"
        />
        <polyline
          points={points}
          fill="none"
          stroke="rgb(59,130,246)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {values.map((v, i) => (
          <circle
            key={i}
            cx={getX(i)}
            cy={getY(v)}
            r={3}
            fill="rgb(59,130,246)"
          />
        ))}
      </svg>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "#9ca3af",
          marginTop: 2,
        }}
      >
        <span>7天前</span>
        <span>今天</span>
      </div>
    </div>
  );
}
