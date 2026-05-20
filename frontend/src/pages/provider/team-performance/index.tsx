// Sprint 9.1 — 服务商团队跨租户绩效汇总（PRD §L2020）
import { useCustom, useGo } from "@refinedev/core";
import { TrendingUp, BadgeDollarSign } from "lucide-react";
import { useState } from "react";

interface MemberPerf {
  user_id: number;
  name: string;
  role: string;
  total_calls: number;
  connected_calls: number;
  promised_cases: number;
  conversion_rate: number | null;
  paid_amount: string;
}

function pct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(1)}%`;
}

// v0.5.6 — ROLE_LABEL 已迁出到 src/lib/roleLabel.ts;服务商团队绩效页 scope=provider
import { roleLabel as roleLabelFn } from "../../../lib/roleLabel";
const ROLE_LABEL = (r: string) => roleLabelFn(r, "provider");

const TOP_N = 10;

export function ProviderTeamPerformancePage() {
  const go = useGo();
  const [period, setPeriod] = useState(30);
  const [showAll, setShowAll] = useState(false);
  const { query } = useCustom<MemberPerf[]>({
    url: "provider/team-performance",
    method: "get",
    config: { query: { period_days: period } },
  });
  const allItems = query.data?.data ?? [];
  // v1.6.4 — 默认 Top 10；超过则显「展开全部」
  const items = showAll ? allItems : allItems.slice(0, TOP_N);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">团队跨租户绩效</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {allItems.length} 名成员
        </span>
        <select
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value={7}>近 7 天</option>
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
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                角色
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                通话总数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                接通数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                承诺数
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                转化率
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                已收金额
              </th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {query.isLoading && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  暂无团队数据
                </td>
              </tr>
            )}
            {items.map((m, idx) => {
              const today = new Date();
              const ym = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
              return (
                <tr key={m.user_id} className="hover:bg-[var(--color-neutral-50)]">
                  <td className="px-4 py-3 text-[var(--color-neutral-400)]">
                    {idx + 1}
                  </td>
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {ROLE_LABEL(m.role)}
                  </td>
                  <td className="px-4 py-3 text-right">{m.total_calls}</td>
                  <td className="px-4 py-3 text-right">{m.connected_calls}</td>
                  <td className="px-4 py-3 text-right">{m.promised_cases}</td>
                  <td className="px-4 py-3 text-right font-medium">
                    {pct(m.conversion_rate)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">
                    ¥{m.paid_amount}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        go({ to: `/provider/team/${m.user_id}/commission?ym=${ym}` })
                      }
                      className="text-[var(--color-primary)] text-xs flex items-center gap-1 ml-auto"
                    >
                      <BadgeDollarSign className="w-3 h-3" />
                      佣金明细
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {allItems.length > TOP_N && (
        <div className="text-right text-xs text-[var(--color-neutral-500)]">
          {showAll ? `共 ${allItems.length} 条` : `仅显示前 ${TOP_N} 名`}{" "}
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="text-[var(--color-primary)] underline"
          >
            {showAll ? "收起" : `查看更多 → 共 ${allItems.length} 条`}
          </button>
        </div>
      )}
    </div>
  );
}
