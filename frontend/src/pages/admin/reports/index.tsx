// 物业管理员 - 数据报表（PRD §3.12 / L2047）
import { useCustom } from "@refinedev/core";
import { TrendingUp, Users, MessageSquareWarning, Target } from "lucide-react";
import { useState } from "react";

interface FunnelStage {
  stage: string;
  label: string;
  count: number;
}

interface AgentPerf {
  user_id: number;
  name: string;
  total_calls: number;
  connected_calls: number;
  promised_cases: number;
  conversion_rate: number | null;
}

interface ObjectionItem {
  intent: string;
  count: number;
}

interface PromiseFollowup {
  total_promised: number;
  total_paid: number;
  rate: number | null;
}

interface ReportOverview {
  period_days: number;
  funnel: FunnelStage[];
  agent_performance: AgentPerf[];
  objection_distribution: ObjectionItem[];
  promise_followup: PromiseFollowup;
}

const PERIOD_OPTIONS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
];

function pct(value: number | null): string {
  if (value === null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

const TOP_N = 10;

export function AdminReportsPage() {
  const [periodDays, setPeriodDays] = useState(30);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const { query } = useCustom<ReportOverview>({
    url: "admin/reports/overview",
    method: "get",
    config: { query: { period_days: periodDays } },
  });
  const data = query.data?.data;

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!data) {
    return <div className="p-6 text-red-600">加载失败，请刷新重试</div>;
  }

  const maxFunnel = Math.max(1, ...data.funnel.map((f) => f.count));
  const maxObjection = Math.max(1, ...data.objection_distribution.map((o) => o.count));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">数据报表</h1>
        </div>
        <select
          value={periodDays}
          onChange={(e) => setPeriodDays(Number(e.target.value))}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          {PERIOD_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      {/* 转化漏斗 */}
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <h2 className="text-base font-semibold mb-4">转化漏斗</h2>
        <div className="space-y-3">
          {data.funnel.map((f) => {
            const w = (f.count / maxFunnel) * 100;
            return (
              <div key={f.stage} className="flex items-center gap-3">
                <span className="w-20 text-sm text-[var(--color-neutral-600)]">
                  {f.label}
                </span>
                <div className="flex-1 bg-[var(--color-neutral-100)] h-6 rounded relative overflow-hidden">
                  <div
                    className="h-full"
                    style={{ width: `${w}%`, background: "var(--color-primary)" }}
                  />
                </div>
                <span className="w-12 text-right text-sm font-medium text-[var(--color-neutral-700)]">
                  {f.count}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 承诺跟进完成率 */}
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">承诺跟进完成率</h2>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Kpi label="承诺总数" value={data.promise_followup.total_promised.toString()} />
          <Kpi label="已缴费" value={data.promise_followup.total_paid.toString()} />
          <Kpi label="完成率" value={pct(data.promise_followup.rate)} highlight />
        </div>
      </section>

      {/* 员工效率 */}
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">员工效率对比</h2>
          <span className="text-xs text-[var(--color-neutral-400)]">
            （{periodDays} 天内）
          </span>
        </div>
        {data.agent_performance.length === 0 ? (
          <p className="text-sm text-[var(--color-neutral-400)]">该时间窗内暂无外呼数据</p>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead className="text-left text-[var(--color-neutral-500)]">
                <tr>
                  <th className="py-2 font-medium">姓名</th>
                  <th className="py-2 font-medium text-right">通话总数</th>
                  <th className="py-2 font-medium text-right">接通数</th>
                  <th className="py-2 font-medium text-right">承诺数</th>
                  <th className="py-2 font-medium text-right">转化率</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-neutral-100)]">
                {(showAllAgents
                  ? data.agent_performance
                  : data.agent_performance.slice(0, TOP_N)
                ).map((a) => (
                  <tr key={a.user_id}>
                    <td className="py-2 font-medium text-[var(--color-neutral-700)]">
                      {a.name}
                    </td>
                    <td className="py-2 text-right">{a.total_calls}</td>
                    <td className="py-2 text-right">{a.connected_calls}</td>
                    <td className="py-2 text-right">{a.promised_cases}</td>
                    <td className="py-2 text-right">{pct(a.conversion_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.agent_performance.length > TOP_N && (
              <div className="text-right text-xs text-[var(--color-neutral-500)] mt-2">
                {showAllAgents
                  ? `共 ${data.agent_performance.length} 名`
                  : `仅显示前 ${TOP_N} 名`}{" "}
                <button
                  type="button"
                  onClick={() => setShowAllAgents((v) => !v)}
                  className="text-[var(--color-primary)] underline"
                >
                  {showAllAgents
                    ? "收起"
                    : `查看更多 → 共 ${data.agent_performance.length} 名`}
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* 异议类型分布 */}
      <section
        className="bg-white p-5 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <MessageSquareWarning className="w-4 h-4 text-[var(--color-primary)]" />
          <h2 className="text-base font-semibold">异议类型分布</h2>
        </div>
        {data.objection_distribution.length === 0 ? (
          <p className="text-sm text-[var(--color-neutral-400)]">暂无 AI 话术反馈数据</p>
        ) : (
          <div className="space-y-2">
            {data.objection_distribution.map((o) => {
              const w = (o.count / maxObjection) * 100;
              return (
                <div key={o.intent} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-[var(--color-neutral-600)]">
                    {o.intent}
                  </span>
                  <div className="flex-1 bg-[var(--color-neutral-100)] h-5 rounded relative overflow-hidden">
                    <div
                      className="h-full"
                      style={{ width: `${w}%`, background: "var(--color-info)" }}
                    />
                  </div>
                  <span className="w-12 text-right text-sm font-medium text-[var(--color-neutral-700)]">
                    {o.count}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function Kpi({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className="p-4 rounded"
      style={{
        background: highlight ? "var(--color-primary-light)" : "var(--color-neutral-50)",
      }}
    >
      <p className="text-xs text-[var(--color-neutral-500)] mb-1">{label}</p>
      <p
        className="text-2xl font-bold"
        style={{
          color: highlight
            ? "var(--color-primary)"
            : "var(--color-neutral-900)",
        }}
      >
        {value}
      </p>
    </div>
  );
}
