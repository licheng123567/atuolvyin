// frontend/src/pages/provider/team/index.tsx
//
// PA.3.3 — Provider team management.
import {
  useCustomMutation,
  useGetIdentity,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { Users } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import type { AuthUser } from "../../../providers/auth-provider";
import { formatDate } from "../helpers";

interface TeamMember {
  user_id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  provider_admin: "服务商管理员",
  legal: "法务专员",
  workorder: "工单处理员",
  agent_external: "兼职催收员",
  project_manager_provider: "项目负责人（服务商）",
};

export function ProviderTeamPage() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<AuthUser>();
  const myUserId = me?.id ?? null;

  const { query } = useList<TeamMember>({
    resource: "provider/team",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: TeamMember[] =
    (rawData as unknown as PaginatedResponse<TeamMember>)?.items ??
    (rawData as TeamMember[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const { mutate: runAction, mutation } = useCustomMutation();
  const actionLoading = mutation.isPending;

  function handleToggle(member: TeamMember) {
    runAction(
      {
        url: `provider/team/${member.user_id}/active`,
        method: "patch",
        values: { is_active: !member.is_active },
      },
      {
        onSuccess: () => {
          void invalidate({
            resource: "provider/team",
            invalidates: ["list"],
          });
        },
        onError: () => {
          alert("操作失败，请稍后重试");
        },
      },
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            团队管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 人
          </span>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                姓名
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                手机号
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                角色
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                加入时间
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
                  暂无团队成员
                </td>
              </tr>
            )}
            {items.map((m) => {
              const isSelf = myUserId !== null && m.user_id === myUserId;
              return (
                <tr
                  key={m.user_id}
                  className="hover:bg-[var(--color-neutral-50)]"
                >
                  <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                    {m.name}
                    {isSelf && (
                      <span className="ml-2 text-xs text-[var(--color-neutral-400)]">
                        （我）
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {m.phone_masked}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {ROLE_LABELS[m.role] ?? m.role}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {formatDate(m.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                      style={
                        m.is_active
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
                      {m.is_active ? "正常" : "停用"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleToggle(m)}
                      disabled={isSelf || actionLoading}
                      className={
                        m.is_active
                          ? "text-red-600 hover:underline text-xs disabled:opacity-30 disabled:cursor-not-allowed disabled:no-underline"
                          : "text-[var(--color-primary)] hover:underline text-xs disabled:opacity-30 disabled:cursor-not-allowed disabled:no-underline"
                      }
                      title={isSelf ? "不能停用自己" : ""}
                    >
                      {m.is_active ? "停用" : "启用"}
                    </button>
                  </td>
                </tr>
              );
            })}
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
