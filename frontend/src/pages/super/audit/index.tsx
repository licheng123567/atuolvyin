// Sprint 15 — Audit log list page (SA.1.8)
import { useList } from "@refinedev/core";
import { FileText, X } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

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

const ACTION_OPTIONS = [
  { value: "", label: "全部操作" },
  { value: "tenant.create", label: "创建租户" },
  { value: "tenant.disable", label: "停用租户" },
  { value: "provider.audit", label: "服务商审核" },
  { value: "settlement.pay", label: "支付结算" },
];

// v0.5.6 — 平台审计日志,actor 可能跨 scope,用 roleLabelAny 兜底
import { roleLabelAny } from "../../../lib/roleLabel";
const ROLE_LABEL = (r: string) => (r === "owner" ? "业主" : roleLabelAny(r));

const PAGE_SIZE = 20;

export function SuperAuditPage() {
  const [action, setAction] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditLogItem | null>(null);

  const filters: { field: string; operator: "eq"; value: string | number }[] = [];
  if (action) filters.push({ field: "action", operator: "eq", value: action });
  if (actorUserId)
    filters.push({
      field: "actor_user_id",
      operator: "eq",
      value: Number.parseInt(actorUserId, 10),
    });
  if (since) filters.push({ field: "since", operator: "eq", value: since });
  if (until) filters.push({ field: "until", operator: "eq", value: until });

  const { query } = useList<AuditLogItem>({
    resource: "super/audit-logs",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const rawData = query.data?.data;
  const items: AuditLogItem[] =
    (rawData as unknown as PaginatedResponse<AuditLogItem>)?.items ??
    (rawData as AuditLogItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 mb-6">
        <FileText className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          平台审计日志
        </h1>
        <span className="text-sm text-[var(--color-neutral-400)] ml-1">
          共 {total} 条
        </span>
      </div>

      {/* Filter form */}
      <div className="bg-white p-4 rounded-lg border border-[var(--color-neutral-200)] mb-4 grid grid-cols-4 gap-3">
        <label className="text-sm">
          <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
            操作类型
          </span>
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
          >
            {ACTION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
            操作人 ID
          </span>
          <input
            type="number"
            value={actorUserId}
            onChange={(e) => {
              setActorUserId(e.target.value);
              setPage(1);
            }}
            className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
          />
        </label>
        <label className="text-sm">
          <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
            起始日期
          </span>
          <input
            type="date"
            value={since}
            onChange={(e) => {
              setSince(e.target.value);
              setPage(1);
            }}
            className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
          />
        </label>
        <label className="text-sm">
          <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
            截止日期
          </span>
          <input
            type="date"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              setPage(1);
            }}
            className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
          />
        </label>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                时间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作人
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                角色
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                目标
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                Payload
              </th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-6 text-center text-[var(--color-neutral-500)]"
                >
                  加载中…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-6 text-center text-[var(--color-neutral-500)]"
                >
                  暂无审计记录
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelected(row)}
                  className="border-b border-[var(--color-neutral-100)] cursor-pointer hover:bg-[var(--color-neutral-50)]"
                >
                  <td className="px-4 py-2 whitespace-nowrap">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">{row.actor_user_id ?? "—"}</td>
                  <td className="px-4 py-2">{row.actor_role ? ROLE_LABEL(row.actor_role) : "—"}</td>
                  <td className="px-4 py-2 font-medium">{row.action}</td>
                  <td className="px-4 py-2">
                    {row.target_type ? `${row.target_type}/${row.target_id ?? "—"}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--color-neutral-500)] truncate max-w-xs">
                    {row.payload ? JSON.stringify(row.payload) : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-3 text-sm text-[var(--color-neutral-600)]">
        <span>
          第 {page} / {totalPages} 页
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-3 py-1.5 border border-[var(--color-neutral-200)] rounded disabled:opacity-50"
          >
            上一页
          </button>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="px-3 py-1.5 border border-[var(--color-neutral-200)] rounded disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      </div>

      {/* Modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-white p-5 rounded-lg w-[600px] max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold">审计详情 #{selected.id}</h2>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="p-1 hover:bg-[var(--color-neutral-100)] rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <pre className="bg-[var(--color-neutral-50)] p-3 rounded text-xs overflow-x-auto">
              {JSON.stringify(selected, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
