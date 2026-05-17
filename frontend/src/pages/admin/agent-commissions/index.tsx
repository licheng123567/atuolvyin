// §9.2 — 内勤提成列表页
import { useGo } from "@refinedev/core";
import { Wallet } from "lucide-react";
import { useState } from "react";
import { Kpi } from "@/components/ui/Kpi";
import { currentYM } from "@/lib/datetime";
import { useAgentCommissions } from "./api";

export function AgentCommissionsListPage() {
  const [ym, setYm] = useState(currentYM());
  const { data, isLoading, isError } = useAgentCommissions(ym);
  const go = useGo();

  const TABLE_COLS = 6;

  return (
    <div className="p-6 space-y-4">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-[var(--color-primary)]" />
          <div>
            <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
              内勤提成
            </h1>
            <p className="text-sm text-[var(--color-neutral-500)]">
              物业内部催收员当月提成（逐案实收 × 项目内勤佣金率）
            </p>
          </div>
        </div>
        <input
          type="month"
          value={ym}
          onChange={(e) => setYm(e.target.value)}
          className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      {/* 加载态 */}
      {isLoading && (
        <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
      )}

      {/* KPI 卡 */}
      {data && (
        <div className="grid grid-cols-2 gap-4">
          <Kpi label="当月总实收基数" value={`¥${data.total_base}`} />
          <Kpi label="当月总应发提成" value={`¥${data.total_commission}`} highlight />
        </div>
      )}

      {/* 表格 */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                催收员
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                已结案数
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                实收基数
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                加权佣金率
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                应发提成
              </th>
              <th className="px-4 py-2 text-center font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载失败
                </td>
              </tr>
            ) : !data || data.items.length === 0 ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  本月无内勤催收员提成数据
                </td>
              </tr>
            ) : (
              data.items.map((item) => (
                <tr key={item.user_id}>
                  <td className="px-4 py-2">
                    <span className="font-medium text-[var(--color-neutral-900)]">
                      {item.name}
                    </span>
                    <br />
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {item.phone_masked}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right text-[var(--color-neutral-700)]">
                    {item.paid_case_count}
                  </td>
                  <td className="px-4 py-2 text-right font-medium">
                    ¥{item.base_amount}
                  </td>
                  <td className="px-4 py-2 text-right text-[var(--color-neutral-600)]">
                    {(item.commission_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-[var(--color-primary)]">
                    ¥{item.commission}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <button
                      type="button"
                      onClick={() =>
                        go({
                          to: `/admin/agent-commissions/${item.user_id}?ym=${ym}`,
                        })
                      }
                      className="text-xs text-[var(--color-primary)] hover:underline"
                    >
                      查看明细
                    </button>
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
