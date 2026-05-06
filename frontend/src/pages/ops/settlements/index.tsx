// Sprint 10.1 — 全平台结算总览（PRD §L1999）
import { useCustom } from "@refinedev/core";
import { DollarSign, AlertTriangle, CheckCircle2 } from "lucide-react";

interface SettlementItem {
  tenant_id: number;
  tenant_name: string;
  period_start: string;
  period_end: string;
  total_amount: string;
  status: "DRAFT" | "CONFIRMED" | "PAID" | "DISPUTED";
  overdue_days: number;
}

interface OverviewOut {
  total_pending: string;
  total_paid_month: string;
  overdue_count: number;
  items: SettlementItem[];
}

const STATUS_LABEL: Record<string, string> = {
  DRAFT: "待确认",
  CONFIRMED: "已确认",
  PAID: "已付款",
  DISPUTED: "有异议",
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  DRAFT: { bg: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  CONFIRMED: { bg: "var(--color-info-light)", color: "var(--color-info)" },
  PAID: { bg: "var(--color-success-light)", color: "var(--color-success)" },
  DISPUTED: { bg: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function OpsSettlementsOverviewPage() {
  const { query } = useCustom<OverviewOut>({
    url: "ops/settlements/overview",
    method: "get",
  });
  const data = query.data?.data;

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!data) {
    return <div className="p-6 text-red-600">加载失败</div>;
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center gap-2">
        <DollarSign className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">全平台结算总览</h1>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <KpiCard
          label="待结算总额"
          value={`¥${data.total_pending}`}
          icon={<DollarSign className="w-4 h-4" />}
        />
        <KpiCard
          label="本月已付款"
          value={`¥${data.total_paid_month}`}
          icon={<CheckCircle2 className="w-4 h-4" />}
          color="var(--color-success)"
        />
        <KpiCard
          label="逾期未付"
          value={String(data.overdue_count)}
          icon={<AlertTriangle className="w-4 h-4" />}
          color={data.overdue_count > 0 ? "var(--color-danger)" : undefined}
        />
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">租户</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">账单周期</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">金额</th>
              <th className="px-4 py-3 text-center font-medium text-[var(--color-neutral-600)]">状态</th>
              <th className="px-4 py-3 text-right font-medium text-[var(--color-neutral-600)]">逾期天数</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  暂无结算单
                </td>
              </tr>
            )}
            {data.items.map((it, i) => {
              const style = STATUS_STYLE[it.status] ?? STATUS_STYLE.DRAFT;
              return (
                <tr key={i} className="hover:bg-[var(--color-neutral-50)]">
                  <td className="px-4 py-3 font-medium">{it.tenant_name}</td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {it.period_start.slice(0, 10)} ~ {it.period_end.slice(0, 10)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">¥{it.total_amount}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                      style={{ background: style.bg, color: style.color }}
                    >
                      {STATUS_LABEL[it.status] ?? it.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {it.overdue_days > 0 ? (
                      <span className="text-red-600 font-medium">
                        {it.overdue_days} 天
                      </span>
                    ) : (
                      <span className="text-[var(--color-neutral-400)]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
}) {
  return (
    <div
      className="bg-white p-4 border border-[var(--color-neutral-200)]"
      style={{ borderRadius: "var(--radius-lg)" }}
    >
      <div className="flex items-center justify-between text-xs text-[var(--color-neutral-500)] mb-1">
        <span>{label}</span>
        <span style={{ color: color ?? "var(--color-neutral-400)" }}>{icon}</span>
      </div>
      <p
        className="text-2xl font-bold"
        style={{ color: color ?? "var(--color-neutral-900)" }}
      >
        {value}
      </p>
    </div>
  );
}
