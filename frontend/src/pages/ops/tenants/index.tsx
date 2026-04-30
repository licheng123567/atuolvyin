import { useGo, useList } from "@refinedev/core";
import { Building2, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface TenantItem {
  id: number;
  name: string;
  plan: string;
  monthly_minute_quota: number | null;
  admin_phone_masked: string;
  is_active: boolean;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: "试用",
  standard: "标准版",
  premium: "高级版",
};

export function TenantListPage() {
  const go = useGo();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { query } = useList<TenantItem>({
    resource: "ops/tenants",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters: q ? [{ field: "q", operator: "eq", value: q }] : [],
  });

  const rawData = query.data?.data;
  const items: TenantItem[] =
    (rawData as unknown as PaginatedResponse<TenantItem>)?.items ??
    (rawData as TenantItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const isLoading = query.isLoading;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            租户管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 家
          </span>
        </div>
        <button
          type="button"
          onClick={() => go({ to: "/ops/tenants/new" })}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white transition-colors"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新建租户
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          placeholder="搜索租户名称…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="w-full pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                租户名称
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                管理员手机
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                套餐
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                月配额（分钟）
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
                  暂无租户数据
                </td>
              </tr>
            )}
            {items.map((t) => (
              <tr key={t.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                  {t.name}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {t.admin_phone_masked}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {PLAN_LABELS[t.plan] ?? t.plan}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {t.monthly_minute_quota ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={
                      t.is_active
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
                    {t.is_active ? "正常" : "停用"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/ops/tenants/${t.id}` })}
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
