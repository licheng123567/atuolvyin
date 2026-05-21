// frontend/src/pages/provider/dashboard/index.tsx
//
// PA.3.1 — Service provider dashboard.
import { useCustom, useCustomMutation } from "@refinedev/core";
import {
  AlertTriangle,
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

interface TerminationStatus {
  contract_id: number;
  status: string;
  termination_requested_by: number | null;
  termination_requested_at: string | null;
  termination_reason: string | null;
  termination_confirmed_at: string | null;
  terminated_at: string | null;
  timeout_days_remaining: number | null;
}

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
  // v1.4 S16.4 — 顶部解约 banner（任何 pending 解约请求或 terminated 合同）
  const { query: termQuery } = useCustom<TerminationStatus[]>({
    url: "provider/contracts",
    method: "get",
  });
  // v1.5.5 — 30 天内即将到期的项目
  const { query: expiringQuery } = useCustom<{ count: number; items: { id: number; name: string; plan_end: string }[] }>({
    url: "provider/projects/expiring",
    method: "get",
  });
  const expiring = expiringQuery.data?.data;
  const contracts = termQuery.data?.data ?? [];
  const incomingRequests = contracts.filter(
    (c) =>
      c.termination_requested_at &&
      !c.termination_confirmed_at &&
      c.status !== "terminated" &&
      c.termination_requested_by === 1, // 1=property
  );
  const ownPendingRequests = contracts.filter(
    (c) =>
      c.termination_requested_at &&
      !c.termination_confirmed_at &&
      c.status !== "terminated" &&
      c.termination_requested_by === 2, // 2=provider
  );
  const recentlyTerminated = contracts.filter(
    (c) => c.status === "terminated" && c.terminated_at,
  );

  const { mutate: termAction, mutation: termMutation } = useCustomMutation();

  const confirmIncoming = (contractId: number) => {
    termAction(
      {
        url: `provider/contracts/${contractId}/terminate-confirm`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => {
          void termQuery.refetch();
        },
      },
    );
  };

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
      {expiring && expiring.count > 0 && (
        <div
          className="flex items-start gap-3 px-4 py-3"
          style={{
            background: "var(--color-warning-light, #fef3c7)",
            border: "1px solid var(--color-warning, #f59e0b)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <AlertTriangle className="w-4 h-4 mt-0.5 text-[var(--color-warning,#f59e0b)]" />
          <div style={{ flex: 1, fontSize: 13 }}>
            <strong>您有 {expiring.count} 个项目将在 30 天内到期</strong>，请联系物业续约。
            <ul style={{ marginTop: 6, paddingLeft: 18, fontSize: 12, color: "var(--color-neutral-600)" }}>
              {expiring.items.map((it) => (
                <li key={it.id}>
                  {it.name} — 服务期至 {it.plan_end ? it.plan_end.slice(0, 10) : "—"}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {(incomingRequests.length > 0 ||
        ownPendingRequests.length > 0 ||
        recentlyTerminated.length > 0) && (
        <div className="space-y-2">
          {incomingRequests.map((c) => (
            <div
              key={`in-${c.contract_id}`}
              className="flex items-start gap-3 px-4 py-3"
              style={{
                background: "var(--color-warning-light, #fef3c7)",
                border: "1px solid var(--color-warning, #f59e0b)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 text-[var(--color-warning,#f59e0b)]" />
              <div style={{ flex: 1, fontSize: 13 }}>
                <strong>租户已申请解约</strong>，请在剩余 {c.timeout_days_remaining ?? 0} 天内确认。逾期将自动转「已终止」。
                {c.termination_reason && (
                  <p style={{ marginTop: 4, color: "var(--color-neutral-600)", fontSize: 12 }}>
                    理由：{c.termination_reason}
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={termMutation.isPending}
                onClick={() => confirmIncoming(c.contract_id)}
                className="px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                style={{
                  background: "var(--color-danger, #ef4444)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                确认解约
              </button>
            </div>
          ))}
          {ownPendingRequests.map((c) => (
            <div
              key={`out-${c.contract_id}`}
              className="px-4 py-3"
              style={{
                background: "var(--color-neutral-100, #f3f4f6)",
                border: "1px solid var(--color-neutral-300, #d1d5db)",
                borderRadius: "var(--radius-md)",
                fontSize: 13,
              }}
            >
              已发起解约请求，等待租户确认（剩余 {c.timeout_days_remaining ?? 0} 天）
            </div>
          ))}
          {recentlyTerminated.map((c) => (
            <div
              key={`done-${c.contract_id}`}
              className="px-4 py-3"
              style={{
                background: "var(--color-danger-light, #fee2e2)",
                border: "1px solid var(--color-danger, #ef4444)",
                borderRadius: "var(--radius-md)",
                fontSize: 13,
              }}
            >
              合作已于 {c.terminated_at?.slice(0, 10)} 终止，30 天内可查阅历史，60 天后数据软删；业主姓名/手机号已不可见。
            </div>
          ))}
        </div>
      )}

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
          label="合作物业"
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
