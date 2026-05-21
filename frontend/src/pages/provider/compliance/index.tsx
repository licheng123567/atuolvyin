// v1.0.0 — 服务商合规月报列表(对齐 admin/compliance/index.tsx)。
import { useCustom, useGo } from "@refinedev/core";
import { FileText, ArrowRight } from "lucide-react";

interface ComplianceListItem {
  year_month: string;
  total_calls: number;
  total_risk_events: number;
  do_not_call_violations: number;
}

export function ProviderComplianceListPage() {
  const go = useGo();
  const { query } = useCustom<ComplianceListItem[]>({
    url: "provider/compliance/monthly",
    method: "get",
    config: { query: { months: 12 } },
  });
  const items = query.data?.data ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 mb-6">
        <FileText className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          合规月报(服务商)
        </h1>
        <span className="text-sm text-[var(--color-neutral-400)] ml-1">
          近 {items.length} 个月
        </span>
        <span className="text-xs text-[var(--color-neutral-500)] ml-3">
          · 范围:本服务商接的所有项目(跨多物业聚合)
        </span>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">月份</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">通话总数</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">风控事件</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">DNC 违规</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {query.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr
                key={it.year_month}
                className="hover:bg-[var(--color-neutral-50)] cursor-pointer"
                onClick={() => go({ to: `/provider/compliance/${it.year_month}` })}
              >
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {it.year_month}
                </td>
                <td className="px-4 py-3 text-right text-[var(--color-neutral-600)]">
                  {it.total_calls}
                </td>
                <td className="px-4 py-3 text-right text-[var(--color-neutral-600)]">
                  {it.total_risk_events}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={
                      it.do_not_call_violations > 0
                        ? "text-red-600 font-medium"
                        : "text-[var(--color-neutral-500)]"
                    }
                  >
                    {it.do_not_call_violations}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <ArrowRight className="w-4 h-4 inline text-[var(--color-neutral-400)]" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ProviderComplianceListPage;
