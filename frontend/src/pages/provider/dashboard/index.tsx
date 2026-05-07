// frontend/src/pages/provider/dashboard/index.tsx
//
// PA.3.1 — Service provider dashboard.
import { useCustom } from "@refinedev/core";
import {
  Building2,
  Calendar,
  DollarSign,
  HourglassIcon,
  LayoutDashboard,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  formatDate,
  formatRevenue,
  getContractStatusColor,
  getContractStatusLabel,
} from "../helpers";

interface ContractSummary {
  tenant_id: number;
  tenant_name: string;
  status: string;
  signed_at: string;
  expires_at: string | null;
}

interface ProviderDashboardStats {
  provider_name: string;
  partner_tenant_count: number;
  team_count: number;
  revenue_month: string | number;
  pending_settlement_total: string | number;
  contracts: ContractSummary[];
}

export function ProviderDashboardPage() {
  const { query } = useCustom<ProviderDashboardStats>({
    url: "provider/dashboard/stats",
    method: "get",
  });
  const isLoading = query.isLoading;
  const isError = query.isError;
  const stats = query.data?.data;

  if (isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (isError || !stats) {
    return (
      <div className="p-6 text-red-600">加载失败，请稍后重试</div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-2">
        <LayoutDashboard className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          服务商总览
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)] ml-2">
          {stats.provider_name}
        </span>
      </div>

      {/* 4 KPI cards */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          label="合作租户"
          value={`${stats.partner_tenant_count}`}
          icon={<Building2 className="w-4 h-4" />}
        />
        <KpiCard
          label="团队人数"
          value={`${stats.team_count}`}
          icon={<Users className="w-4 h-4" />}
        />
        <KpiCard
          label="本月收入"
          value={formatRevenue(stats.revenue_month)}
          icon={<DollarSign className="w-4 h-4" />}
          tone="success"
        />
        <KpiCard
          label="待结算金额"
          value={formatRevenue(stats.pending_settlement_total)}
          icon={<HourglassIcon className="w-4 h-4" />}
          tone={Number(stats.pending_settlement_total) > 0 ? "warn" : "default"}
        />
      </div>

      {/* Top 10 contracts */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-neutral-200)] flex items-center gap-2">
          <Calendar className="w-4 h-4 text-[var(--color-neutral-500)]" />
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)]">
            合作合同（最近 10 份）
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)]">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-[var(--color-neutral-600)]">
                租户
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-[var(--color-neutral-600)]">
                状态
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-[var(--color-neutral-600)]">
                签约日期
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-[var(--color-neutral-600)]">
                到期日期
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {(stats.contracts ?? []).length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无合作合同
                </td>
              </tr>
            )}
            {(stats.contracts ?? []).map((c) => (
              <tr
                key={`${c.tenant_id}-${c.signed_at}`}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {c.tenant_name}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getContractStatusColor(c.status)}`}
                  >
                    {getContractStatusLabel(c.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatDate(c.signed_at)}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatDate(c.expires_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "warn";
}

function KpiCard({ label, value, icon, tone = "default" }: KpiCardProps) {
  const toneClass =
    tone === "success"
      ? "border-green-200 bg-green-50"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50"
        : "border-[var(--color-neutral-200)] bg-white";
  const valueClass =
    tone === "success"
      ? "text-green-700"
      : tone === "warn"
        ? "text-amber-700"
        : "text-[var(--color-neutral-900)]";
  return (
    <div className={`rounded-lg border p-4 ${toneClass}`}>
      <div className="flex items-center gap-1.5 text-xs text-[var(--color-neutral-600)]">
        {icon}
        {label}
      </div>
      <div className={`text-2xl font-semibold mt-2 ${valueClass}`}>{value}</div>
    </div>
  );
}
