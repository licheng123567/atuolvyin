// frontend/src/pages/admin/settlements/index.tsx
import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Receipt, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  formatAmount,
  formatPeriod,
  getStatusColor,
  recentYearMonths,
  STATUS_LABELS,
  type SettlementStatus,
} from "./helpers";

interface SettlementItem {
  id: number;
  contract_id: number;
  provider_id: number | null;
  provider_name: string | null;
  period_start: string;
  period_end: string;
  total_amount: string;
  status: SettlementStatus;
  payment_proof_url: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
}

const STATUS_OPTIONS: { value: "" | SettlementStatus; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "DRAFT", label: STATUS_LABELS.DRAFT },
  { value: "CONFIRMED", label: STATUS_LABELS.CONFIRMED },
  { value: "PAID", label: STATUS_LABELS.PAID },
  { value: "DISPUTED", label: STATUS_LABELS.DISPUTED },
];

export function AdminSettlementListPage() {
  const go = useGo();
  const [statusFilter, setStatusFilter] = useState<"" | SettlementStatus>("");
  const [yearMonth, setYearMonth] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const yearMonthOptions = useMemo(() => recentYearMonths(6), []);

  const filters: CrudFilter[] = [];
  if (statusFilter) {
    filters.push({ field: "status", operator: "eq", value: statusFilter });
  }
  if (yearMonth) {
    filters.push({ field: "year_month", operator: "eq", value: yearMonth });
  }

  const { query } = useList<SettlementItem>({
    resource: "admin/settlements",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: SettlementItem[] = useMemo(
    () =>
      (rawData as unknown as PaginatedResponse<SettlementItem>)?.items ??
      (rawData as SettlementItem[] | undefined) ??
      [],
    [rawData],
  );
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  // KPIs computed from current page items (for MVP simplicity).
  const kpis = useMemo(() => {
    let pendingCount = 0;
    let pendingAmount = 0;
    let paidCount = 0;
    let paidAmount = 0;
    let disputedCount = 0;
    for (const it of items) {
      const amt = Number(it.total_amount) || 0;
      if (it.status === "CONFIRMED" || it.status === "DRAFT") {
        pendingCount += 1;
        pendingAmount += amt;
      } else if (it.status === "PAID") {
        paidCount += 1;
        paidAmount += amt;
      } else if (it.status === "DISPUTED") {
        disputedCount += 1;
      }
    }
    return { pendingCount, pendingAmount, paidCount, paidAmount, disputedCount };
  }, [items]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Receipt className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            结算管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 张
          </span>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <KpiCard
          label="本月待支付"
          value={`${kpis.pendingCount} 张 · ${formatAmount(kpis.pendingAmount)}`}
        />
        <KpiCard
          label="已支付"
          value={`${kpis.paidCount} 张 · ${formatAmount(kpis.paidAmount)}`}
          tone="success"
        />
        <KpiCard
          label="争议中"
          value={`${kpis.disputedCount} 张`}
          tone={kpis.disputedCount > 0 ? "danger" : "default"}
        />
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as "" | SettlementStatus);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <select
          value={yearMonth}
          onChange={(e) => {
            setYearMonth(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部月份</option>
          {yearMonthOptions.map((ym) => (
            <option key={ym} value={ym}>
              {ym}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                期间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                服务商
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                金额
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                状态
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无结算单
                </td>
              </tr>
            )}
            {items.map((s) => (
              <tr
                key={s.id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3 text-[var(--color-neutral-900)] font-medium">
                  {formatPeriod(s.period_start, s.period_end)}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {s.provider_name ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-900)]">
                  {formatAmount(s.total_amount)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getStatusColor(s.status)}`}
                  >
                    {STATUS_LABELS[s.status] ?? s.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/admin/settlements/${s.id}` })}
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    查看详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  tone?: "default" | "success" | "danger";
}

function KpiCard({ label, value, tone = "default" }: KpiCardProps) {
  const toneClass =
    tone === "success"
      ? "border-green-200 bg-green-50"
      : tone === "danger"
        ? "border-red-200 bg-red-50"
        : "border-[var(--color-neutral-200)] bg-white";
  const valueClass =
    tone === "success"
      ? "text-green-700"
      : tone === "danger"
        ? "text-red-700"
        : "text-[var(--color-neutral-900)]";
  return (
    <div className={`rounded-lg border p-4 ${toneClass}`}>
      <div className="text-xs text-[var(--color-neutral-600)]">{label}</div>
      <div className={`text-lg font-semibold mt-2 ${valueClass}`}>{value}</div>
    </div>
  );
}
