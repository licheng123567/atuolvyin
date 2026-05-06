// Sprint 10.4 — 平台运营员个人操作日志（PRD §L2002）
import { useCustom } from "@refinedev/core";
import { History } from "lucide-react";
import { useState } from "react";

interface AuditLogItem {
  id: number;
  actor_user_id: number | null;
  actor_role: string | null;
  tenant_id: number | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

interface PaginatedAuditLogs {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export function OpsMyAuditLogsPage() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { query } = useCustom<PaginatedAuditLogs>({
    url: "ops/audit-logs/me",
    method: "get",
    config: { query: { page, page_size: PAGE_SIZE } },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <History className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">我的操作日志</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {total} 条
        </span>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">时间</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">动作</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">租户</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">目标</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">payload</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {query.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-neutral-400)]">
                  无操作记录
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 text-[var(--color-neutral-500)] text-xs">
                  {it.created_at?.slice(0, 19).replace("T", " ")}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{it.action}</td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {it.tenant_id ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {it.target_type
                    ? `${it.target_type} #${it.target_id ?? "—"}`
                    : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-500)] max-w-[300px]">
                  <code className="line-clamp-2">
                    {it.payload ? JSON.stringify(it.payload) : "—"}
                  </code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <button
            type="button"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-3 py-1.5 border border-[var(--color-neutral-200)] disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page === totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="px-3 py-1.5 border border-[var(--color-neutral-200)] disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
