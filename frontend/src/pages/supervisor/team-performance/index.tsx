// Sprint 9.5 — 主管督导团队绩效（PRD §L2069）
import { useCustom } from "@refinedev/core";
import { TrendingUp, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { useState } from "react";

interface TeamPerfItem {
  user_id: number;
  name: string;
  total_calls: number;
  connected_calls: number;
  promised_cases: number;
  paid_cases: number;
  conversion_rate: number | null;
  delta_vs_previous: number | null;
}

interface TeamPerfOut {
  period_days: number;
  items: TeamPerfItem[];
}

function pct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(1)}%`;
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) {
    return <span className="text-xs text-[var(--color-neutral-400)]">—</span>;
  }
  if (Math.abs(delta) < 0.01) {
    return (
      <span className="inline-flex items-center text-xs text-[var(--color-neutral-500)]">
        <Minus className="w-3 h-3 mr-0.5" /> 0%
      </span>
    );
  }
  const positive = delta > 0;
  return (
    <span
      className="inline-flex items-center text-xs font-medium"
      style={{
        color: positive ? "var(--color-success)" : "var(--color-danger)",
      }}
    >
      {positive ? (
        <ArrowUpRight className="w-3 h-3 mr-0.5" />
      ) : (
        <ArrowDownRight className="w-3 h-3 mr-0.5" />
      )}
      {Math.abs(delta * 100).toFixed(1)}%
    </span>
  );
}

export function SupervisorTeamPerformancePage() {
  const [period, setPeriod] = useState(7);
  const { query } = useCustom<TeamPerfOut>({
    url: "supervisor/team-performance",
    method: "get",
    config: { query: { period_days: period } },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">团队绩效</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {items.length} 名坐席
        </span>
        <select
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value={7}>近 7 天</option>
          <option value={14}>近 14 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)] w-12">
                #
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                姓名
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                通话总数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                vs 上期
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                接通数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                承诺数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                已缴费
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                转化率
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {query.isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  本组暂无坐席数据
                </td>
              </tr>
            )}
            {items.map((it, idx) => (
              <tr key={it.user_id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 text-[var(--color-neutral-400)] font-medium">
                  {idx + 1}
                </td>
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {it.name}
                </td>
                <td className="px-4 py-3 text-right">{it.total_calls}</td>
                <td className="px-4 py-3 text-right">
                  <DeltaBadge delta={it.delta_vs_previous} />
                </td>
                <td className="px-4 py-3 text-right">{it.connected_calls}</td>
                <td className="px-4 py-3 text-right">{it.promised_cases}</td>
                <td className="px-4 py-3 text-right">{it.paid_cases}</td>
                <td className="px-4 py-3 text-right font-medium">
                  {pct(it.conversion_rate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
