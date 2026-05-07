// Sprint 15 — Cost dashboard (SA.★)
import { useCustom } from "@refinedev/core";
import { TrendingUp } from "lucide-react";
import { formatMinutes, formatPercent } from "../helpers";

interface TenantUsage {
  tenant_id: number;
  name: string;
  used_minutes: number;
  quota: number | null;
  utilization_pct: number;
}

interface MonthlyTrendPoint {
  year_month: string;
  total_used: number;
}

interface CostDashboard {
  total_quota_pool: number;
  total_used_this_month: number;
  tenant_ranking: TenantUsage[];
  monthly_trend: MonthlyTrendPoint[];
}

export function SuperCostPage() {
  const { query } = useCustom<CostDashboard>({
    url: "super/cost/dashboard",
    method: "get",
  });

  if (query.isLoading) return <div className="p-6 text-neutral-500">加载中…</div>;
  if (query.isError || !query.data?.data)
    return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;

  const raw = query.data.data as Partial<typeof query.data.data>;
  // 防御 server response 字段缺失
  const stats = {
    total_quota_pool: raw.total_quota_pool ?? 0,
    total_used_this_month: raw.total_used_this_month ?? 0,
    monthly_trend: raw.monthly_trend ?? [],
    tenant_ranking: raw.tenant_ranking ?? [],
  };
  const usagePct =
    stats.total_quota_pool > 0
      ? (stats.total_used_this_month / stats.total_quota_pool) * 100
      : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          成本看板
        </h1>
      </div>

      {/* KPI cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 16,
        }}
      >
        <KpiCard
          label="总配额池（分钟/月）"
          value={formatMinutes(stats.total_quota_pool)}
        />
        <KpiCard
          label="本月已用（分钟）"
          value={formatMinutes(stats.total_used_this_month)}
          sub={`使用率 ${formatPercent(usagePct)}`}
        />
      </div>

      {/* Trend chart */}
      <div
        className="bg-white p-4 rounded-lg border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-md)" }}
      >
        <h2 className="text-base font-medium mb-3">近 6 个月用量趋势</h2>
        <TrendChart points={stats.monthly_trend} />
      </div>

      {/* Ranking table */}
      <div
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden"
        style={{ borderRadius: "var(--radius-md)" }}
      >
        <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] text-base font-medium">
          租户使用排行 (Top 10)
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                #
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                租户名称
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                已用 (分钟)
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                配额
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                使用率
              </th>
            </tr>
          </thead>
          <tbody>
            {stats.tenant_ranking.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-6 text-center text-[var(--color-neutral-500)]"
                >
                  暂无数据
                </td>
              </tr>
            ) : (
              stats.tenant_ranking.map((t: TenantUsage, i: number) => (
                <tr
                  key={t.tenant_id}
                  className="border-b border-[var(--color-neutral-100)]"
                >
                  <td className="px-4 py-2">{i + 1}</td>
                  <td className="px-4 py-2 font-medium">{t.name}</td>
                  <td className="px-4 py-2 text-right">
                    {formatMinutes(t.used_minutes)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {formatMinutes(t.quota)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span
                      className={
                        t.utilization_pct >= 100
                          ? "text-red-600"
                          : t.utilization_pct >= 80
                            ? "text-yellow-600"
                            : "text-[var(--color-neutral-700)]"
                      }
                    >
                      {formatPercent(t.utilization_pct)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div
      className="bg-white p-4 rounded-lg border border-[var(--color-neutral-200)]"
      style={{ borderRadius: "var(--radius-md)" }}
    >
      <div className="text-xs text-[var(--color-neutral-500)]">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {sub && (
        <div className="text-xs text-[var(--color-neutral-400)] mt-1">{sub}</div>
      )}
    </div>
  );
}

function TrendChart({ points }: { points: MonthlyTrendPoint[] }) {
  const width = 600;
  const height = 160;
  const pad = 28;
  const max = Math.max(1, ...points.map((p) => p.total_used));
  const stepX = (width - pad * 2) / Math.max(1, points.length - 1);
  const coords = points.map((p, i) => {
    const x = pad + i * stepX;
    const y = height - pad - (p.total_used / max) * (height - pad * 2);
    return { x, y, ym: p.year_month, used: p.total_used };
  });
  const path = coords
    .map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`)
    .join(" ");

  return (
    <svg width={width} height={height} role="img" aria-label="月度用量趋势">
      <line
        x1={pad}
        y1={height - pad}
        x2={width - pad}
        y2={height - pad}
        stroke="#E5E7EB"
      />
      <path d={path} fill="none" stroke="#3B82F6" strokeWidth={2} />
      {coords.map((c) => (
        <g key={c.ym}>
          <circle cx={c.x} cy={c.y} r={3} fill="#3B82F6" />
          <text
            x={c.x}
            y={height - pad + 14}
            textAnchor="middle"
            fontSize={10}
            fill="#6B7280"
          >
            {c.ym.slice(5)}
          </text>
        </g>
      ))}
    </svg>
  );
}
