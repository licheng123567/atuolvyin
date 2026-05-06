// frontend/src/pages/provider/tenants/index.tsx
//
// PA.3.2 — Partner tenants list (provider's signed contracts).
import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Building2, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  formatDate,
  getContractStatusColor,
  getContractStatusLabel,
} from "../helpers";

interface ProviderTenantItem {
  tenant_id: number;
  name: string;
  contract_id: number;
  signed_at: string;
  expires_at: string | null;
  status: string;
  service_types: string[];
}

const SERVICE_TYPE_LABELS: Record<string, string> = {
  legal: "法务催收",
  collection: "外呼催收",
  both: "综合服务",
};

const STATUS_OPTIONS: { value: ""; label: string }[] | { value: string; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "active", label: "履约中" },
  { value: "expired", label: "已到期" },
];

export function ProviderTenantsPage() {
  const go = useGo();
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (q) filters.push({ field: "q", operator: "eq", value: q });
  if (statusFilter)
    filters.push({ field: "status", operator: "eq", value: statusFilter });

  const { query } = useList<ProviderTenantItem>({
    resource: "provider/tenants",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: ProviderTenantItem[] =
    (rawData as unknown as PaginatedResponse<ProviderTenantItem>)?.items ??
    (rawData as ProviderTenantItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            合作租户
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 家
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索租户名称…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
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
                租户名
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                签约日期
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                到期日期
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                服务类型
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
                  colSpan={6}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无合作租户
                </td>
              </tr>
            )}
            {items.map((t) => (
              <tr
                key={t.contract_id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {t.name}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatDate(t.signed_at)}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatDate(t.expires_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {t.service_types.map((s) => (
                      <span
                        key={s}
                        className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium bg-blue-100 text-blue-700"
                      >
                        {SERVICE_TYPE_LABELS[s] ?? s}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getContractStatusColor(t.status)}`}
                  >
                    {getContractStatusLabel(t.status)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() =>
                      go({
                        to: "/provider/settlements",
                        query: { tenant_id: t.tenant_id.toString() },
                      })
                    }
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    查看结算
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
