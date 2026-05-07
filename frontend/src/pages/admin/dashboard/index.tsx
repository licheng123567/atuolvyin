// 1:1 还原 ui/admin.html#a-dashboard 管理看板
import { useCustom } from "@refinedev/core";
import { TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { formatMinutes, formatCurrency } from "./helpers";

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

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

function formatDate(d: Date): string {
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 星期${WEEKDAYS[d.getDay()]}`;
}

interface ProjectKpi {
  project_id: number;
  project_name: string;
  provider_id: number | null;
  provider_name: string | null;
  case_count: number;
  receivable: number;
  received: number;
  recovery_rate: number;
  promised_count: number;
  in_progress_count: number;
  new_count: number;
  escalated_count: number;
  closed_count: number;
  connected_30d: number;
  total_calls_30d: number;
}

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const { query } = useCustom<DashboardStats>({
    url: "admin/dashboard/stats",
    method: "get",
  });
  const stats = query.data?.data;

  const { query: projectKpiQuery } = useCustom<ProjectKpi[]>({
    url: "admin/dashboard/by-project",
    method: "get",
  });
  const projectKpiRaw = projectKpiQuery.data?.data;
  const projectKpis: ProjectKpi[] = Array.isArray(projectKpiRaw)
    ? projectKpiRaw
    : ((projectKpiRaw as unknown as { items?: ProjectKpi[] })?.items ?? []);

  if (query.isLoading) return <div className="p-6 text-neutral-500">加载中…</div>;
  if (query.isError || !stats)
    return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;

  const today = stats.today ?? {
    outbound_count: 0,
    connected_count: 0,
    promised_count: 0,
    recovered_amount: 0,
  };
  const quota = stats.minute_quota ?? {
    used_min: 0,
    total_min: 0,
    remaining_min: null,
    warning: false,
  };
  const topAgents = stats.top_agents ?? [];
  const scriptTrend = stats.script_adoption_trend ?? [];

  const connectedRate =
    today.outbound_count > 0
      ? `${((today.connected_count / today.outbound_count) * 100).toFixed(1)}%`
      : "—";
  const usedPct =
    quota.total_min && quota.total_min > 0
      ? Math.min(100, (quota.used_min / quota.total_min) * 100)
      : 0;
  const remainingMin =
    quota.remaining_min ??
    (quota.total_min ? Math.max(0, quota.total_min - quota.used_min) : null);

  // 本周 AI 采用率：取最后一天 + 与第一天差值
  const latestRate = scriptTrend.length > 0 ? scriptTrend[scriptTrend.length - 1] : 0;
  const firstRate = scriptTrend.length > 0 ? scriptTrend[0] : 0;
  const rateDelta = (latestRate - firstRate) * 100;

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">管理看板</h1>
          <div className="page-subtitle">{formatDate(new Date())}</div>
        </div>
      </div>

      {/* v1.4 S16.6 — P1 待充实预览栏：reports / compliance 数据稀疏，下版本充实 */}
      <div
        style={{
          background: "var(--color-warning-light, #fef3c7)",
          border: "1px solid var(--color-warning, #f59e0b)",
          borderRadius: "var(--radius-md)",
          padding: "10px 14px",
          marginBottom: 16,
          fontSize: 13,
          color: "var(--color-neutral-700, #374151)",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontWeight: 600 }}>📊 P1 预览功能</span>
        <span>
          「数据报表」「合规月报」已上线但 demo 数据稀疏，v1.5 补充后转 P0；其他菜单均为 P0 正式版。
        </span>
      </div>

      {/* 5 KPI cards */}
      <div
        className="stat-grid"
        style={{ gridTemplateColumns: "repeat(5,1fr)" }}
      >
        <StatCard
          label="今日外呼"
          value={today.outbound_count}
          changeUp="较昨日 +12%"
        />
        <StatCard
          label="今日接通"
          value={today.connected_count}
          changeNeutral={`接通率 ${connectedRate}`}
        />
        <StatCard
          label="今日承诺缴费"
          value={today.promised_count}
          changeNeutral={`金额 ${formatCurrency(today.recovered_amount)}`}
        />
        <StatCard
          label="今日实际回款"
          value={formatCurrency(today.recovered_amount)}
          valueFontSize={22}
          changeUp="较昨日 +23%"
        />
        {/* 配额警告卡：橙色高亮 + 进度条 */}
        <div
          className="stat-card"
          style={{
            borderColor: "var(--color-warning)",
            background: "#fffbeb",
          }}
        >
          <div className="stat-label" style={{ color: "#92400e" }}>
            本月通话分钟
          </div>
          <div
            className="stat-value"
            style={{ fontSize: 22, color: "#d97706" }}
          >
            {formatMinutes(quota.used_min)}
          </div>
          <div style={{ fontSize: 12, color: "#92400e", marginTop: 4 }}>
            配额 {quota.total_min ? formatMinutes(quota.total_min) : "—"} 分钟
          </div>
          <div
            style={{
              background: "#fde68a",
              borderRadius: 4,
              height: 5,
              marginTop: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                background: "#d97706",
                height: "100%",
                width: `${usedPct}%`,
                borderRadius: 4,
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: "#92400e", marginTop: 3 }}>
            已用 {usedPct.toFixed(1)}%
            {remainingMin != null
              ? `，剩余 ${formatMinutes(remainingMin)} 分钟`
              : ""}
          </div>
        </div>
      </div>

      {/* Two-column main */}
      <div className="two-col">
        {/* Left: ranking table */}
        <div className="ds-card">
          <div className="card-header">
            <span className="card-title">全员今日排名</span>
            <span className="text-sm text-muted">实时更新</span>
          </div>
          <div
            className="table-wrap"
            style={{ border: "none", boxShadow: "none", borderRadius: 0 }}
          >
            <table>
              <thead>
                <tr>
                  <th>排名</th>
                  <th>姓名</th>
                  <th>通话数</th>
                  <th>承诺数</th>
                  <th>回款金额</th>
                  <th>AI 采用率</th>
                </tr>
              </thead>
              <tbody>
                {topAgents.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      style={{
                        textAlign: "center",
                        color: "#9ca3af",
                        padding: 24,
                      }}
                    >
                      暂无数据
                    </td>
                  </tr>
                )}
                {topAgents.map((a, i) => (
                  <tr key={a.user_id}>
                    <td>
                      <RankBadge rank={i + 1} />
                    </td>
                    <td>{a.name}</td>
                    <td>{a.today_calls} 次</td>
                    <td>{a.month_promised} 单</td>
                    <td>—</td>
                    <td>
                      <span className="ds-badge ds-badge-blue">—</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: stacked cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* 公海待分配 */}
          <div
            className="ds-card"
            style={{ background: "#fff7ed", borderColor: "#fed7aa" }}
          >
            <div
              className="card-body"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12,
                    color: "#92400e",
                    fontWeight: 600,
                  }}
                >
                  公海待分配案件
                </div>
                <div
                  style={{
                    fontSize: 32,
                    fontWeight: 700,
                    color: "#ea580c",
                  }}
                >
                  {stats.public_pool_count}
                </div>
                <div style={{ fontSize: 12, color: "#92400e" }}>个</div>
              </div>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                onClick={() => navigate("/admin/pool")}
              >
                立即分配
              </button>
            </div>
          </div>

          {/* AI 话术采用率周柱图 */}
          <div className="ds-card">
            <div className="card-header">
              <span className="card-title">AI 话术采用率（本周）</span>
            </div>
            <div className="card-body">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <span
                  style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: "#1A56DB",
                  }}
                >
                  {(latestRate * 100).toFixed(0)}%
                </span>
                {scriptTrend.length >= 2 && (
                  <span
                    className={`ds-badge ${
                      rateDelta >= 0 ? "ds-badge-green" : "ds-badge-red"
                    }`}
                    style={{ fontSize: 11 }}
                  >
                    <TrendingUp className="w-3 h-3" />
                    {rateDelta >= 0 ? "↑" : "↓"}
                    {Math.abs(rateDelta).toFixed(1)}%
                  </span>
                )}
              </div>
              <WeekBarChart values={scriptTrend} />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11,
                  color: "#9ca3af",
                  marginTop: 4,
                }}
              >
                <span>7 天前</span>
                <span>今天</span>
              </div>
            </div>
          </div>

          {/* 风控告警分级 */}
          <div className="ds-card">
            <div className="card-header">
              <span className="card-title">本周风控告警</span>
            </div>
            <div
              className="card-body"
              style={{ display: "flex", gap: 16 }}
            >
              <RiskCell label="L1 注意" count={stats.risk_alert_count_7d} color="#d97706" />
              <RiskCell label="L2 警告" count={0} color="#e02424" />
              <RiskCell label="L3 紧急" count={0} color="#6b7280" />
            </div>
          </div>
        </div>
      </div>

      {/* v1.4 — 按项目统计 */}
      {projectKpis.length > 0 && (
        <div className="ds-card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <span className="card-title">按项目分维度</span>
            <span className="text-sm text-muted">
              共 {projectKpis.length} 个项目
            </span>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <div className="table-wrap" style={{ borderRadius: 0, border: "none" }}>
              <table>
                <thead>
                  <tr>
                    <th>项目名称</th>
                    <th>合作服务商</th>
                    <th style={{ textAlign: "right" }}>案件数</th>
                    <th style={{ textAlign: "right" }}>应收</th>
                    <th style={{ textAlign: "right" }}>已收</th>
                    <th style={{ textAlign: "right" }}>回款率</th>
                    <th>阶段分布</th>
                    <th style={{ textAlign: "right" }}>30 天接通</th>
                    <th style={{ width: 80 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {projectKpis.map((p) => {
                    const connectedRate =
                      p.total_calls_30d > 0
                        ? (p.connected_30d / p.total_calls_30d) * 100
                        : 0;
                    return (
                      <tr key={p.project_id}>
                        <td>
                          <strong>{p.project_name}</strong>
                        </td>
                        <td>
                          {p.provider_name ?? (
                            <span style={{ color: "#9ca3af" }}>自营</span>
                          )}
                        </td>
                        <td style={{ textAlign: "right" }}>{p.case_count}</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>
                          ¥{p.receivable.toLocaleString()}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            fontWeight: 600,
                            color: "#057a55",
                          }}
                        >
                          ¥{p.received.toLocaleString()}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <span
                            style={{
                              color:
                                p.recovery_rate > 0.5
                                  ? "#057a55"
                                  : p.recovery_rate > 0.2
                                    ? "#d97706"
                                    : "#9ca3af",
                              fontWeight: 600,
                            }}
                          >
                            {(p.recovery_rate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td style={{ fontSize: 11, color: "#6b7280" }}>
                          新 {p.new_count} · 跟 {p.in_progress_count} · 诺{" "}
                          {p.promised_count} · 升 {p.escalated_count} · 结{" "}
                          {p.closed_count}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {p.connected_30d}/{p.total_calls_30d}{" "}
                          <span style={{ fontSize: 11, color: "#9ca3af" }}>
                            ({connectedRate.toFixed(0)}%)
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            onClick={() =>
                              navigate(`/admin/cases?project_id=${p.project_id}`)
                            }
                          >
                            查看案件
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── sub-components ──────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  valueFontSize?: number;
  changeUp?: string;
  changeNeutral?: string;
}

function StatCard({
  label,
  value,
  valueFontSize,
  changeUp,
  changeNeutral,
}: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div
        className="stat-value"
        style={valueFontSize ? { fontSize: valueFontSize } : undefined}
      >
        {value}
      </div>
      {changeUp && (
        <div className="stat-change up">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
            <polyline points="17 6 23 6 23 12" />
          </svg>
          {changeUp}
        </div>
      )}
      {changeNeutral && (
        <div className="stat-change neutral">{changeNeutral}</div>
      )}
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const medal: Record<number, string> = {
    1: "#fbbf24",
    2: "#9ca3af",
    3: "#cd7c2c",
  };
  const bg = medal[rank];
  if (bg) {
    return (
      <span
        style={{
          background: bg,
          color: "white",
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
  return (
    <span style={{ color: "#6b7280", paddingLeft: 12 }}>{rank}</span>
  );
}

function WeekBarChart({ values }: { values: number[] }) {
  // 没数据：占位 7 个空柱
  const data = values.length > 0 ? values : Array.from({ length: 7 }, () => 0);
  const max = Math.max(...data, 0.01);
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        alignItems: "flex-end",
        height: 48,
      }}
    >
      {data.slice(0, 7).map((v, i) => {
        const pct = (v / max) * 100;
        return (
          <div
            key={i}
            style={{
              flex: 1,
              background: "#dbeafe",
              borderRadius: "3px 3px 0 0",
              height: "100%",
              display: "flex",
              alignItems: "flex-end",
            }}
            title={`第 ${i + 1} 天 ${(v * 100).toFixed(0)}%`}
          >
            <div
              style={{
                width: "100%",
                height: `${pct}%`,
                background: "#1A56DB",
                borderRadius: "3px 3px 0 0",
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

function RiskCell({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{count}</div>
      <div style={{ fontSize: 12, color: "#6b7280" }}>{label}</div>
    </div>
  );
}
