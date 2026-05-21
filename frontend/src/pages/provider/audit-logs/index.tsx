// v1.0.0 — 服务商审计日志(对齐物业 admin/audit-logs 简化版)。
//
// 查看本服务商成员的所有操作 + 与本服务商接的案件相关的所有操作(target_type=case 兜底)。
import { useCustom } from "@refinedev/core";
import { ScrollText, Search, X } from "lucide-react";
import { useState } from "react";
import { roleLabelAny } from "../../../lib/roleLabel";

interface AuditLogItem {
  id: number;
  actor_user_id: number | null;
  actor_role: string | null;
  tenant_id: number | null;
  provider_id: number | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

interface AuditLogList {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

const ACTION_LABEL: Record<string, string> = {
  "case.assigned": "案件分配",
  "case.reassigned": "案件重派",
  "case.released": "案件释放",
  "case.auto_released_stale": "自动释放(久未联系)",
  "case.imported": "导入案件",
  "provider_settings.update": "更新系统配置",
  "settlement.created": "生成结算单",
  "settlement.confirmed": "确认结算",
  "settlement.paid": "标记已付",
  "script.created": "新建话术",
  "script.updated": "更新话术",
};

export function ProviderAuditLogPage() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 30;
  const [actionFilter, setActionFilter] = useState("");

  const { query } = useCustom<AuditLogList>({
    url: "provider/audit-logs",
    method: "get",
    config: {
      query: {
        page,
        page_size: PAGE_SIZE,
        action: actionFilter || undefined,
      },
    },
  });
  const data = query.data?.data;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <ScrollText className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            审计日志(服务商)
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 条
          </span>
        </div>
      </div>

      <p className="text-xs text-[var(--color-neutral-500)] mb-4">
        范围:本服务商成员的操作 +
        与本服务商接的案件相关的所有操作(物业 admin / 督导 对本服务商案件的动作也会展示)
      </p>

      {/* 过滤栏 */}
      <div className="flex items-center gap-2 mb-4 p-3 bg-white border border-[var(--color-neutral-200)] rounded-md">
        <Search className="w-4 h-4 text-[var(--color-neutral-400)]" />
        <input
          type="text"
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(1);
          }}
          placeholder="按 action 前缀过滤(如 case. 或 case.reassigned)"
          className="flex-1 text-sm border-none outline-none bg-transparent"
        />
        {actionFilter && (
          <button
            type="button"
            onClick={() => {
              setActionFilter("");
              setPage(1);
            }}
            className="p-1 hover:bg-[var(--color-neutral-100)] rounded"
            title="清除过滤"
          >
            <X className="w-3.5 h-3.5 text-[var(--color-neutral-500)]" />
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">时间</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">操作人</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">操作</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">目标</th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">备注</th>
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
                  暂无审计日志
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.id} className="hover:bg-[var(--color-neutral-50)]">
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-700)] font-mono">
                  {new Date(it.created_at).toLocaleString("zh-CN")}
                </td>
                <td className="px-4 py-3 text-xs">
                  {it.actor_user_id ? (
                    <>
                      user #{it.actor_user_id}
                      {it.actor_role && (
                        <span className="ml-1 text-[var(--color-neutral-500)]">
                          ({roleLabelAny(it.actor_role)})
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-[var(--color-neutral-400)]">系统</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-neutral-100)] text-[var(--color-neutral-700)] font-mono">
                    {ACTION_LABEL[it.action] ?? it.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {it.target_type ? (
                    <>
                      {it.target_type}
                      {it.target_id != null && (
                        <span className="ml-1 font-mono">#{it.target_id}</span>
                      )}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-500)] max-w-md truncate">
                  {it.payload
                    ? Object.entries(it.payload)
                        .filter(([k]) => k !== "note" || it.payload?.[k])
                        .slice(0, 3)
                        .map(([k, v]) => `${k}=${String(v).slice(0, 30)}`)
                        .join(" / ")
                    : "—"}
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
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1.5 text-sm border rounded disabled:opacity-40"
            style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1.5 text-sm border rounded disabled:opacity-40"
            style={{ borderColor: "var(--color-neutral-200)", borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

export default ProviderAuditLogPage;
