// §9 — 内勤提成单人逐案明细页
import { useGo } from "@refinedev/core";
import { ArrowLeft, Wallet } from "lucide-react";
import { useParams, useSearchParams } from "react-router-dom";
import { Kpi } from "@/components/ui/Kpi";
import { currentYM } from "@/lib/datetime";
import { useAgentCommissionDetail } from "./api";

const TABLE_COLS = 4;

export function AgentCommissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const [searchParams] = useSearchParams();
  const ym = searchParams.get("ym") ?? currentYM();
  const go = useGo();

  const { data, isLoading, isError } = useAgentCommissionDetail(userId || undefined, ym);

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <p className="text-sm text-[var(--color-danger)]">未找到提成明细</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      {/* 返回链接 */}
      <button
        type="button"
        onClick={() => go({ to: "/admin/agent-commissions" })}
        className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)]"
      >
        <ArrowLeft className="w-4 h-4" /> 返回内勤提成列表
      </button>

      {/* 页头 */}
      <div className="flex items-center gap-2">
        <Wallet className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            内勤提成明细 · {data.name}
          </h1>
          <p className="text-sm text-[var(--color-neutral-500)]">
            {ym} · 逐案「实收 × 项目内勤佣金率」
          </p>
        </div>
      </div>

      {/* KPI 卡 */}
      <div className="grid grid-cols-3 gap-4">
        <Kpi label="实收基数（扣已执行减免）" value={`¥${data.base_amount}`} />
        <Kpi
          label="加权佣金率"
          value={`${(data.commission_rate * 100).toFixed(1)}%`}
        />
        <Kpi label="应发提成" value={`¥${data.commission}`} highlight />
      </div>

      {/* 逐案明细表格 */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                案件（业主）
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                项目佣金率
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                实收金额
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                缴清时间
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {data.items.length === 0 ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  本月该催收员无已结案件
                </td>
              </tr>
            ) : (
              data.items.map((it) => (
                <tr key={it.case_id}>
                  <td className="px-4 py-2 text-[var(--color-neutral-900)]">
                    {it.owner_name}
                  </td>
                  <td className="px-4 py-2 text-right text-[var(--color-neutral-600)]">
                    {(Number(it.commission_rate) * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-right font-medium">
                    ¥{it.paid_amount}
                  </td>
                  <td className="px-4 py-2 text-[var(--color-neutral-500)]">
                    {it.paid_at.slice(0, 10)}
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
