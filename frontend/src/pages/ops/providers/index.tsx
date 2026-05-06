import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Briefcase, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  AUDIT_STATUS_LABELS,
  formatAuditStatus,
  formatProviderType,
  getAuditStatusColor,
  type AuditStatus,
} from "./helpers";

interface ProviderItem {
  id: number;
  name: string;
  provider_type: string;
  admin_phone_masked: string;
  contact_email: string | null;
  monthly_minute_quota: number | null;
  is_active: boolean;
  audit_status: string;
  audit_at: string | null;
  created_at: string;
}

const STATUS_OPTIONS: { value: "" | AuditStatus; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "pending", label: AUDIT_STATUS_LABELS.pending },
  { value: "approved", label: AUDIT_STATUS_LABELS.approved },
  { value: "rejected", label: AUDIT_STATUS_LABELS.rejected },
];

export function ProviderListPage() {
  const go = useGo();
  const [q, setQ] = useState("");
  const [auditStatus, setAuditStatus] = useState<"" | AuditStatus>("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (q) filters.push({ field: "q", operator: "eq", value: q });
  if (auditStatus)
    filters.push({ field: "audit_status", operator: "eq", value: auditStatus });

  const { query } = useList<ProviderItem>({
    resource: "ops/providers",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: ProviderItem[] =
    (rawData as unknown as PaginatedResponse<ProviderItem>)?.items ??
    (rawData as ProviderItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            服务商管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 家
          </span>
        </div>
        <button
          type="button"
          onClick={() => go({ to: "/ops/providers/new" })}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新增服务商
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索服务商名称或11位手机号…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)", minWidth: "240px" }}
          />
        </div>
        <select
          value={auditStatus}
          onChange={(e) => {
            setAuditStatus(e.target.value as "" | AuditStatus);
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
                名称
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                类型
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                管理员手机
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                月配额（分钟）
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                审核状态
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                运营状态
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
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无服务商数据
                </td>
              </tr>
            )}
            {items.map((p) => (
              <tr key={p.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {p.name}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatProviderType(p.provider_type)}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {p.admin_phone_masked}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {p.monthly_minute_quota ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getAuditStatusColor(p.audit_status)}`}
                  >
                    {formatAuditStatus(p.audit_status)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={
                      p.is_active
                        ? {
                            background: "var(--color-success-light)",
                            color: "var(--color-success)",
                          }
                        : {
                            background: "var(--color-danger-light)",
                            color: "var(--color-danger)",
                          }
                    }
                  >
                    {p.is_active ? "正常" : "停用"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/ops/providers/${p.id}` })}
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
