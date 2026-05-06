import { useCreate, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Briefcase, KanbanSquare, List, Plus, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface OwnerInfo {
  id: number;
  name: string;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

interface CaseItem {
  id: number;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  status: string;
}

interface AgentItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待处理",
  in_progress: "处理中",
  promised: "已承诺",
  paid: "已缴费",
  escalated: "已上报",
  closed: "已关闭",
};

const POOL_LABELS: Record<string, string> = {
  public: "公池",
  private: "专属",
};

const STAGE_COLORS: Record<string, React.CSSProperties> = {
  new: { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  in_progress: { background: "var(--color-primary-light)", color: "var(--color-primary)" },
  promised: { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  paid: { background: "var(--color-success-light)", color: "var(--color-success)" },
  escalated: { background: "var(--color-danger-light)", color: "var(--color-danger)" },
  closed: { background: "var(--color-neutral-100)", color: "var(--color-neutral-400)" },
};

export function CaseListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [poolType, setPoolType] = useState("");
  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "keyword", operator: "eq", value: keyword });
  if (poolType) filters.push({ field: "pool_type", operator: "eq", value: poolType });
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });

  const { query } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const { query: agentsQuery } = useList<AgentItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
    queryOptions: { enabled: assignModalOpen },
  });

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const rawAgents = agentsQuery.data?.data;
  const agents: AgentItem[] =
    (rawAgents as unknown as PaginatedResponse<AgentItem>)?.items ??
    (rawAgents as AgentItem[] | undefined) ??
    [];

  const { mutate: assignCases, mutation: assignMutation } = useCreate();
  const assigning = assignMutation.isPending;

  function handleToggleSelect(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function handleAssign() {
    if (!selectedAgentId || selectedIds.length === 0) return;
    assignCases(
      {
        resource: "admin/cases/assign",
        values: { case_ids: selectedIds, assign_to: selectedAgentId },
      },
      {
        onSuccess: () => {
          setAssignModalOpen(false);
          setSelectedIds([]);
          setSelectedAgentId(null);
          query.refetch();
        },
      }
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            案件管理
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 件
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* List / Kanban toggle */}
          <div className="flex items-center gap-1 border border-[var(--color-neutral-200)] rounded-md overflow-hidden">
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
              style={{ background: "var(--color-primary)" }}
            >
              <List className="w-4 h-4" />
              列表
            </button>
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases/kanban" })}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)]"
            >
              <KanbanSquare className="w-4 h-4" />
              看板
            </button>
          </div>

          {selectedIds.length > 0 && (
            <button
              type="button"
              onClick={() => setAssignModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium border border-[var(--color-primary)] text-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              <UserCheck className="w-4 h-4" />
              分配 ({selectedIds.length})
            </button>
          )}
          <button
            type="button"
            onClick={() => go({ to: "/admin/cases/import" })}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Plus className="w-4 h-4" />
            导入案件
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-neutral-400)]" />
          <input
            type="text"
            placeholder="搜索业主姓名…"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] w-48"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
        <select
          value={poolType}
          onChange={(e) => {
            setPoolType(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部池</option>
          <option value="public">公池</option>
          <option value="private">专属</option>
        </select>
        <select
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <option value="">全部阶段</option>
          {Object.entries(STAGE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-3 py-3 w-8">
                <input
                  type="checkbox"
                  checked={
                    selectedIds.length === items.length && items.length > 0
                  }
                  onChange={(e) =>
                    setSelectedIds(
                      e.target.checked ? items.map((i) => i.id) : []
                    )
                  }
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                业主
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                房间
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                欠费(元)
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                逾期月数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                阶段
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                池
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
                  colSpan={8}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无案件数据
                </td>
              </tr>
            )}
            {items.map((c) => (
              <tr
                key={c.id}
                className={`hover:bg-[var(--color-neutral-50)] ${
                  selectedIds.includes(c.id) ? "bg-blue-50" : ""
                }`}
              >
                <td className="px-3 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(c.id)}
                    onChange={() => handleToggleSelect(c.id)}
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--color-neutral-900)]">
                    {c.owner.name}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-400)]">
                    {c.owner.phone_masked}
                  </div>
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.owner.building && c.owner.room
                    ? `${c.owner.building} ${c.owner.room}`
                    : (c.owner.building ?? c.owner.room ?? "—")}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.amount_owed ?? "—"}
                </td>
                <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                  {c.months_overdue ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
                    style={STAGE_COLORS[c.stage] ?? {}}
                  >
                    {STAGE_LABELS[c.stage] ?? c.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-[var(--color-neutral-600)]">
                  {POOL_LABELS[c.pool_type] ?? c.pool_type}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => go({ to: `/admin/cases/${c.id}` })}
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

      {/* Assign Modal */}
      {assignModalOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div
            className="bg-white p-6 w-96 shadow-lg"
            style={{ borderRadius: "var(--radius-lg)" }}
          >
            <h2 className="text-lg font-semibold text-[var(--color-neutral-900)] mb-4">
              分配案件（共 {selectedIds.length} 件）
            </h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                选择催收员
              </label>
              <select
                value={selectedAgentId ?? ""}
                onChange={(e) =>
                  setSelectedAgentId(Number(e.target.value) || null)
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                <option value="">请选择</option>
                {agents
                  .filter((a) =>
                    ["agent_internal", "agent_external"].includes(a.role)
                  )
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}（{a.phone_masked}）
                    </option>
                  ))}
              </select>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setAssignModalOpen(false);
                  setSelectedAgentId(null);
                }}
                className="px-4 py-2 text-sm border border-[var(--color-neutral-200)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                取消
              </button>
              <button
                type="button"
                disabled={!selectedAgentId || assigning}
                onClick={handleAssign}
                className="px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                style={{
                  background: "var(--color-primary)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                {assigning ? "分配中…" : "确认分配"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
