// v1.6.4 — 督导团队报表
import { useCustom } from "@refinedev/core";
import { BarChart2, Download } from "lucide-react";
import { useState } from "react";
import { LeaderboardTopN } from "../../../components/ui/LeaderboardTopN";

interface TrendPoint {
  date: string;
  outbound: number;
  connected: number;
}
interface Funnel {
  outbound: number;
  connected: number;
  promised: number;
  paid: number;
}
interface TeamMember {
  user_id: number;
  name: string;
  calls: number;
  connected: number;
  connect_rate: number;
  promises: number;
  paid_amount: string;
}
interface TeamStats {
  period_start: string;
  period_end: string;
  period_days: number;
  call_trend: TrendPoint[];
  funnel: Funnel;
  team_ranking: TeamMember[];
}

const PERIODS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
];

function pct(num: number, den: number): string {
  if (!den) return "—";
  return `${((num / den) * 100).toFixed(1)}%`;
}

export function SupervisorStatsPage() {
  const [period, setPeriod] = useState(30);
  const { query } = useCustom<TeamStats>({
    url: "supervisor/team-stats",
    method: "get",
    config: { query: { period_days: period } },
    queryOptions: { staleTime: 60_000 },
  });
  const data = query.data?.data;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">团队报表</div>
          <div className="page-subtitle">
            {data
              ? `${data.period_start} ~ ${data.period_end}`
              : "周期性绩效统计与数据导出"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <div
            style={{
              display: "inline-flex",
              border: "1px solid var(--color-neutral-200)",
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPeriod(p.value)}
                style={{
                  padding: "6px 14px",
                  fontSize: 13,
                  background:
                    period === p.value ? "var(--color-primary)" : "white",
                  color: period === p.value ? "white" : "var(--color-neutral-700)",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            onClick={() => window.print()}
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            <Download className="w-3.5 h-3.5" />
            导出（打印 / PDF）
          </button>
        </div>
      </div>

      {query.isLoading && (
        <div className="ds-card">
          <div className="card-body" style={{ padding: 24, color: "var(--color-neutral-400)" }}>
            加载中…
          </div>
        </div>
      )}

      {!query.isLoading && !data && (
        <div className="ds-card">
          <div className="card-body" style={{ padding: 24, color: "var(--color-danger)" }}>
            加载失败，请刷新重试
          </div>
        </div>
      )}

      {data && (
        <>
          {/* 漏斗 */}
          <div className="ds-card section-gap">
            <div className="card-header">
              <span className="card-title">回款转化漏斗</span>
            </div>
            <div
              className="card-body"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: 12,
              }}
            >
              <FunnelStep label="拨打" value={data.funnel.outbound} color="#3b82f6" />
              <FunnelStep
                label="接通"
                value={data.funnel.connected}
                rate={pct(data.funnel.connected, data.funnel.outbound)}
                color="#06b6d4"
              />
              <FunnelStep
                label="承诺"
                value={data.funnel.promised}
                rate={pct(data.funnel.promised, data.funnel.connected)}
                color="#f59e0b"
              />
              <FunnelStep
                label="缴清"
                value={data.funnel.paid}
                rate={pct(data.funnel.paid, data.funnel.promised)}
                color="#10b981"
              />
            </div>
          </div>

          {/* 趋势 */}
          <div className="ds-card section-gap">
            <div className="card-header">
              <span className="card-title">通话量趋势</span>
              <span className="text-sm text-muted">
                按天 · 蓝线=拨打 / 绿线=接通
              </span>
            </div>
            <div className="card-body">
              {data.call_trend.length === 0 ? (
                <div style={{ color: "var(--color-neutral-400)", fontSize: 13 }}>
                  本周期内暂无通话数据
                </div>
              ) : (
                <TrendChart points={data.call_trend} />
              )}
            </div>
          </div>

          {/* 团队排名 */}
          <div className="ds-card">
            <div className="card-header">
              <span className="card-title">
                <BarChart2
                  className="w-4 h-4"
                  style={{ display: "inline", marginRight: 6, verticalAlign: "-2px" }}
                />
                团队成员排名
              </span>
              <span className="text-sm text-muted">
                共 {data.team_ranking.length} 名活跃成员
              </span>
            </div>
            <div style={{ padding: "0 16px 16px" }}>
              <LeaderboardTopN
                rows={data.team_ranking}
                topN={10}
                emptyText="本周期内无成员通话数据"
                columns={[
                  { key: "rank", label: "排名", width: 50 },
                  { key: "name", label: "姓名" },
                  { key: "calls", label: "通话数", align: "right" },
                  { key: "rate", label: "接通率", align: "right" },
                  { key: "promises", label: "承诺数", align: "right" },
                  { key: "paid", label: "缴清金额", align: "right" },
                ]}
                renderRow={(m, idx) => (
                  <tr key={m.user_id}>
                    <td>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 24,
                          height: 24,
                          borderRadius: "50%",
                          fontSize: 11,
                          fontWeight: 700,
                          background:
                            idx === 0
                              ? "#fef3c7"
                              : idx === 1
                                ? "#e5e7eb"
                                : idx === 2
                                  ? "#fed7aa"
                                  : "transparent",
                          color:
                            idx === 0
                              ? "#92400e"
                              : idx === 1
                                ? "#374151"
                                : idx === 2
                                  ? "#9a3412"
                                  : "#9ca3af",
                        }}
                      >
                        {idx + 1}
                      </span>
                    </td>
                    <td>{m.name}</td>
                    <td style={{ textAlign: "right" }}>{m.calls}</td>
                    <td style={{ textAlign: "right" }}>
                      {(m.connect_rate * 100).toFixed(1)}%
                    </td>
                    <td style={{ textAlign: "right" }}>{m.promises}</td>
                    <td
                      style={{
                        textAlign: "right",
                        fontWeight: 600,
                        color: "#057a55",
                      }}
                    >
                      ¥{Number(m.paid_amount).toLocaleString()}
                    </td>
                  </tr>
                )}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function FunnelStep({
  label,
  value,
  rate,
  color,
}: {
  label: string;
  value: number;
  rate?: string;
  color: string;
}) {
  return (
    <div
      style={{
        padding: 12,
        borderRadius: 6,
        background: "white",
        borderLeft: `4px solid ${color}`,
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>
        {value.toLocaleString()}
      </div>
      {rate && (
        <div style={{ fontSize: 11, color, marginTop: 2 }}>
          转化率 {rate}
        </div>
      )}
    </div>
  );
}

function TrendChart({ points }: { points: TrendPoint[] }) {
  // 简易 SVG 折线（不引入 chart 库）
  const W = 720;
  const H = 220;
  const PAD = 32;
  const maxY = Math.max(
    1,
    ...points.flatMap((p) => [p.outbound, p.connected]),
  );
  const xStep = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
  const yScale = (v: number) => H - PAD - (v / maxY) * (H - PAD * 2);

  const path = (key: "outbound" | "connected") =>
    points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${PAD + i * xStep} ${yScale(p[key])}`)
      .join(" ");

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H} style={{ minWidth: W }}>
        {/* y 轴刻度 */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = H - PAD - t * (H - PAD * 2);
          return (
            <g key={t}>
              <line
                x1={PAD}
                y1={y}
                x2={W - PAD}
                y2={y}
                stroke="#e5e7eb"
                strokeDasharray="2 2"
              />
              <text x={4} y={y + 3} fontSize={10} fill="#9ca3af">
                {Math.round(maxY * t)}
              </text>
            </g>
          );
        })}
        {/* 拨打线（蓝） */}
        <path d={path("outbound")} fill="none" stroke="#3b82f6" strokeWidth={2} />
        {/* 接通线（绿） */}
        <path d={path("connected")} fill="none" stroke="#10b981" strokeWidth={2} />
        {/* 数据点 */}
        {points.map((p, i) => (
          <g key={p.date}>
            <circle cx={PAD + i * xStep} cy={yScale(p.outbound)} r={3} fill="#3b82f6" />
            <circle cx={PAD + i * xStep} cy={yScale(p.connected)} r={3} fill="#10b981" />
            {(i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 6) === 0) && (
              <text
                x={PAD + i * xStep}
                y={H - PAD + 14}
                fontSize={10}
                fill="#6b7280"
                textAnchor="middle"
              >
                {p.date.slice(5)}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
