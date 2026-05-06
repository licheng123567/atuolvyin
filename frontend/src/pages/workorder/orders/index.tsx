import { useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { ClipboardList, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  WORK_ORDER_STATUSES,
  WORK_ORDER_TYPES,
  formatStatus,
  formatType,
  getStatusColor,
} from "./helpers";

interface WorkOrderItem {
  id: number;
  case_id: number | null;
  call_id: number | null;
  order_type: string;
  description: string;
  assigned_to: number | null;
  status: string;
  resolution: string | null;
  assignee_name: string | null;
  created_at: string;
}

export function WorkOrderListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  if (statusFilter)
    filters.push({ field: "status", operator: "eq", value: statusFilter });
  if (typeFilter)
    filters.push({ field: "order_type", operator: "eq", value: typeFilter });

  const { query } = useList<WorkOrderItem>({
    resource: "workorders",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: WorkOrderItem[] =
    (rawData as unknown as PaginatedResponse<WorkOrderItem>)?.items ??
    (rawData as WorkOrderItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <ClipboardList className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            工单管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 单
          </span>
        </div>
        <button
          type="button"
          onClick={() => go({ to: "/workorder/orders/new" })}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新建工单
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索描述…"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] w-48"
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
          <option value="">全部状态</option>
          {WORK_ORDER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {formatStatus(s)}
            </option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部类型</option>
          {WORK_ORDER_TYPES.map((t) => (
            <option key={t} value={t}>
              {formatType(t)}
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
                工单号
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                类型
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                描述
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                状态
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                负责人
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                关联案件
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
                  暂无工单
                </td>
              </tr>
            )}
            {items.map((wo) => (
              <tr
                key={wo.id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  #{wo.id}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {formatType(wo.order_type)}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-700)] max-w-xs truncate">
                  {wo.description}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={getStatusColor(wo.status)}
                  >
                    {formatStatus(wo.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {wo.assignee_name ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {wo.case_id ? `#${wo.case_id}` : "—"}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/workorder/orders/${wo.id}` })}
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] disabled:opacity-40"
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
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
