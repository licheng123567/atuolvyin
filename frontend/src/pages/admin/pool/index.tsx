import {
  useCustomMutation,
  useGo,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { Users } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  created_at: string;
}

interface UserItem {
  id: number;
  name: string;
  role: string;
}

export function AdminPoolPage() {
  const [assignFor, setAssignFor] = useState<number | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);
  const invalidate = useInvalidate();
  const go = useGo();

  const { query: casesQuery } = useList<CaseItem>({
    resource: "admin/cases",
    filters: [{ field: "pool_type", operator: "eq", value: "public" }],
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const rawCases = casesQuery.data?.data;
  const allCases: CaseItem[] =
    (rawCases as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawCases as CaseItem[] | undefined) ??
    [];

  // Sort by priority_score desc, then amount_owed desc (backend may not support ordering)
  const cases = [...allCases].sort(
    (a, b) =>
      b.priority_score - a.priority_score ||
      parseFloat(b.amount_owed ?? "0") - parseFloat(a.amount_owed ?? "0"),
  );

  const isLoading = casesQuery.isLoading;

  // Load all agents for the assign modal and private-pool overview
  const { data: agentsData } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const rawAgents = agentsData?.data;
  const allUsers: UserItem[] =
    (rawAgents as unknown as PaginatedResponse<UserItem>)?.items ??
    (rawAgents as UserItem[] | undefined) ??
    [];

  // Filter to agents only (agent_internal and agent_external)
  const agents = allUsers.filter((u) => u.role.startsWith("agent_"));

  const { mutate: assign } = useCustomMutation();

  const handleAssign = () => {
    if (assignFor === null || selectedAgent === null) return;
    assign(
      {
        url: "admin/cases/assign",
        method: "post",
        values: { case_ids: [assignFor], assign_to: selectedAgent },
      },
      {
        onSuccess: () => {
          setAssignFor(null);
          setSelectedAgent(null);
          void invalidate({
            resource: "admin/cases",
            invalidates: ["list"],
          });
        },
        onError: () => {
          alert("分配失败，请重试");
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
        公海案件管理
      </h1>

      {/* Public pool case table */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                业主
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                欠费(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                逾期月数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                优先级
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                创建时间
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
            {!isLoading && cases.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  公海无案件
                </td>
              </tr>
            )}
            {cases.map((c) => (
              <tr
                key={c.id}
                className="hover:bg-[var(--color-neutral-50)]"
              >
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/admin/cases/${c.id}` })}
                    className="font-medium text-[var(--color-primary)] hover:underline text-left"
                  >
                    {c.owner.name}
                  </button>
                  {(c.owner.building ?? c.owner.room) && (
                    <div className="text-xs text-[var(--color-neutral-400)]">
                      {[c.owner.building, c.owner.room].filter(Boolean).join(" ")}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_owed != null ? `¥${c.amount_owed}` : "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.months_overdue ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.priority_score}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {new Date(c.created_at).toLocaleDateString("zh-CN")}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => setAssignFor(c.id)}
                    className="text-[var(--color-primary)] hover:underline text-xs"
                  >
                    分配
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Private pool overview — one row per agent */}
      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4">
        <h3 className="font-semibold mb-2 flex items-center gap-2 text-[var(--color-neutral-900)]">
          <Users className="w-4 h-4 text-[var(--color-primary)]" />
          各员工私海数量
        </h3>
        {/* TODO(v1.1): 拉 user.case_count 字段后展示真实数量 */}
        {agents.length === 0 ? (
          <p className="text-sm text-[var(--color-neutral-400)]">暂无催收员</p>
        ) : (
          <ul className="text-sm space-y-1">
            {agents.map((a) => (
              <li
                key={a.id}
                className="flex justify-between border-b border-[var(--color-neutral-100)] py-1 last:border-0"
              >
                <span className="text-[var(--color-neutral-700)]">{a.name}</span>
                <span className="text-[var(--color-neutral-400)]">
                  私海案件数：—
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Release rules — static card */}
      <div
        className="rounded-lg p-4 text-sm text-[var(--color-neutral-600)]"
        style={{ background: "var(--color-neutral-50)" }}
      >
        {/* TODO(v1.1): 实现真规则可配置 */}
        <strong className="text-[var(--color-neutral-700)]">释放规则：</strong>
        <p className="mt-1">30 天未联系自动回公海（v1.1 可配置）。</p>
      </div>

      {/* Assign modal */}
      {assignFor !== null && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          role="dialog"
          aria-modal="true"
          aria-label="分配案件"
        >
          <div
            className="bg-white p-6 w-96 shadow-lg"
            style={{ borderRadius: "var(--radius-lg)" }}
          >
            <h2 className="text-lg font-semibold text-[var(--color-neutral-900)] mb-4">
              分配案件
            </h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                选择催收员
              </label>
              {agents.length === 0 ? (
                <p className="text-sm text-[var(--color-neutral-400)]">
                  暂无可用催收员
                </p>
              ) : (
                <select
                  className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                  style={{ borderRadius: "var(--radius-md)" }}
                  value={selectedAgent ?? ""}
                  onChange={(e) =>
                    setSelectedAgent(Number(e.target.value) || null)
                  }
                >
                  <option value="">— 选择员工 —</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                      {a.role === "agent_internal"
                        ? "（内部）"
                        : a.role === "agent_external"
                          ? "（外部）"
                          : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setAssignFor(null);
                  setSelectedAgent(null);
                }}
                className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleAssign}
                disabled={selectedAgent === null}
                className="px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                style={{
                  background: "var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                确认分配
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
