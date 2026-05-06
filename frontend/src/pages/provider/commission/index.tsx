// Sprint 9.2 — 服务商成员单月佣金明细（PRD §L2021）
import { useCustom, useGo } from "@refinedev/core";
import { ArrowLeft, BadgeDollarSign } from "lucide-react";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

interface CommissionLineItem {
  case_id: number;
  owner_name: string;
  paid_amount: string;
  paid_at: string | null;
}

interface CommissionOut {
  user_id: number;
  name: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  commission: string;
  items: CommissionLineItem[];
}

function currentYM(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ProviderMemberCommissionPage() {
  const { user_id } = useParams<{ user_id: string }>();
  const [searchParams] = useSearchParams();
  const initialYm = searchParams.get("ym") ?? currentYM();
  const go = useGo();
  const [ym, setYm] = useState(initialYm);

  const { query } = useCustom<CommissionOut>({
    url: `provider/team/${user_id}/commission`,
    method: "get",
    config: { query: { year_month: ym } },
  });
  const data = query.data?.data;

  return (
    <div className="p-6 space-y-4">
      <button
        type="button"
        onClick={() => go({ to: "/provider/team-performance" })}
        className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)]"
      >
        <ArrowLeft className="w-4 h-4" /> 返回团队绩效
      </button>

      <div className="flex items-center gap-2">
        <BadgeDollarSign className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">
          {data?.name ?? "成员"} - 佣金明细
        </h1>
        <input
          type="month"
          value={ym}
          onChange={(e) => setYm(e.target.value)}
          className="ml-auto px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      {query.isLoading && (
        <p className="text-sm text-[var(--color-neutral-400)]">加载中…</p>
      )}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Kpi label="计算基数（已缴费）" value={`¥${data.base_amount}`} />
            <Kpi
              label="佣金费率"
              value={`${(data.commission_rate * 100).toFixed(1)}%`}
            />
            <Kpi
              label="佣金金额"
              value={`¥${data.commission}`}
              highlight
            />
          </div>

          <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] text-sm font-semibold">
              {ym} 月已缴费案件 · 共 {data.items.length} 单
            </div>
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                    案件 ID
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                    业主
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                    缴费金额
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                    缴费时间
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-neutral-100)]">
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                      该月无已缴费案件
                    </td>
                  </tr>
                )}
                {data.items.map((it) => (
                  <tr key={it.case_id}>
                    <td className="px-4 py-2 font-mono text-xs">#{it.case_id}</td>
                    <td className="px-4 py-2">{it.owner_name}</td>
                    <td className="px-4 py-2 text-right font-medium">
                      ¥{it.paid_amount}
                    </td>
                    <td className="px-4 py-2 text-[var(--color-neutral-500)]">
                      {it.paid_at?.slice(0, 19).replace("T", " ") ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
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
        background: highlight
          ? "var(--color-primary-light)"
          : "var(--color-neutral-50)",
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
