// 1:1 还原 ui/admin.html#a-cases CRM 案件列表
import { useCreate, useCustom, useGetIdentity, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { CheckSquare, KanbanSquare, List, Plus, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { AuthUser } from "../../../providers/auth-provider";
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
  project_id: number | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  status: string;
  notes: string | null;
  last_contact_at?: string | null;
  case_no?: string | null;
}

interface ProjectOption {
  id: number;
  name: string;
}

interface AgentItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
}

const STAGE_LABELS: Record<string, string> = {
  new: "待联系",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级中",
  closed: "已关闭",
  legal: "法务处理",
};

// badge color → 原型中阶段→颜色
const STAGE_BADGE_CLASS: Record<string, string> = {
  new: "ds-badge ds-badge-gray",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-orange",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  legal: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

function formatLastContact(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const day = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (day === 0) return "今天";
  if (day === 1) return "昨天";
  if (day < 7) return `${day}天前`;
  if (day < 14) return "1周前";
  if (day < 30) return `${Math.floor(day / 7)}周前`;
  return d.toISOString().slice(0, 10);
}

export function CaseListPage() {
  const go = useGo();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectIdParam = searchParams.get("project_id");
  const projectIdFilter = projectIdParam ? Number(projectIdParam) : null;
  const { data: identity } = useGetIdentity<AuthUser>();
  const isPM =
    identity?.role === "project_manager_property" ||
    identity?.role === "project_manager_provider";

  const [keyword, setKeyword] = useState("");
  const [stage, setStage] = useState("");
  const [agentFilter, setAgentFilter] = useState<number | "">("");
  const [buildingFilter, setBuildingFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const PAGE_SIZE = 12;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "keyword", operator: "eq", value: keyword });
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });
  if (projectIdFilter !== null) {
    filters.push({ field: "project_id", operator: "eq", value: projectIdFilter });
  }
  if (agentFilter !== "") {
    filters.push({ field: "assigned_to", operator: "eq", value: agentFilter });
  }
  if (buildingFilter) {
    filters.push({ field: "building", operator: "eq", value: buildingFilter });
  }

  const { query } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  // 当前项目（用于页头显示）
  const { query: projectQuery } = useList<ProjectOption>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
    queryOptions: { enabled: projectIdFilter !== null },
  });
  const projectsRaw = projectQuery.data?.data;
  const allProjects: ProjectOption[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectOption>)?.items ??
    (projectsRaw as ProjectOption[] | undefined) ??
    [];
  const currentProject = allProjects.find((p) => p.id === projectIdFilter);

  // 楼栋下拉数据：从 GET /admin/cases/buildings 拿，按当前项目过滤
  const { query: buildingsQuery } = useCustom<string[]>({
    url: "admin/cases/buildings",
    method: "get",
    config: {
      query: projectIdFilter !== null ? { project_id: projectIdFilter } : {},
    },
  });
  const buildings: string[] = buildingsQuery.data?.data ?? [];

  // 员工下拉：始终拉，用于过滤 + 批量分配
  const { query: agentsQuery } = useList<AgentItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const rawData = query.data?.data;
  const items: CaseItem[] =
    (rawData as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData as CaseItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isLoading = query.isLoading;

  const rawAgents = agentsQuery.data?.data;
  const allAgents: AgentItem[] =
    (rawAgents as unknown as PaginatedResponse<AgentItem>)?.items ??
    (rawAgents as AgentItem[] | undefined) ??
    [];
  // 只看催收员（内勤 + 兼职），过滤下拉与批量分配下拉都用
  const agents = allAgents.filter(
    (a) => a.role === "agent_internal" || a.role === "agent_external",
  );

  const { mutate: assignCases, mutation: assignMutation } = useCreate();
  const assigning = assignMutation.isPending;

  function handleToggleSelect(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
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
      },
    );
  }

  // 分页：原型呈现 1 2 3 … 8 ›
  const paginationButtons = renderPaginationPages(page, totalPages, setPage);

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {currentProject ? `${currentProject.name} · 案件列表` : "CRM 案件列表"}
          </h1>
          <div className="page-subtitle">
            共 {total} 个案件
            {projectIdFilter !== null && (
              <button
                type="button"
                onClick={() => {
                  searchParams.delete("project_id");
                  setSearchParams(searchParams);
                  setPage(1);
                }}
                style={{
                  marginLeft: 12,
                  fontSize: 12,
                  color: "var(--color-primary)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                ← 返回全部项目
              </button>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {/* 列表/看板切换 */}
          <div
            style={{
              display: "flex",
              border: "1px solid var(--color-neutral-200)",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
            }}
          >
            <button
              type="button"
              className="ds-btn ds-btn-primary ds-btn-sm"
              style={{ borderRadius: 0 }}
            >
              <List className="w-3.5 h-3.5" />
              列表
            </button>
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases/kanban" })}
              className="ds-btn ds-btn-secondary ds-btn-sm"
              style={{ border: "none", borderRadius: 0 }}
            >
              <KanbanSquare className="w-3.5 h-3.5" />
              看板
            </button>
          </div>
          {!isPM && selectedIds.length > 0 && (
            <button
              type="button"
              onClick={() => setAssignModalOpen(true)}
              className="ds-btn ds-btn-secondary"
            >
              <UserCheck className="w-3.5 h-3.5" />
              批量分配（{selectedIds.length}）
            </button>
          )}
          {!isPM && (
            <button
              type="button"
              onClick={() => go({ to: "/admin/cases/import" })}
              className="ds-btn ds-btn-primary"
            >
              <Plus className="w-3.5 h-3.5" />
              导入案件
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="table-wrap">
        {/* Toolbar */}
        <div className="table-toolbar">
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              type="text"
              className="form-control"
              placeholder="搜索业主姓名 / 房号 / 案件编号"
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setPage(1);
              }}
              style={{ minWidth: 240 }}
            />
          </div>
          <select
            className="form-control"
            style={{ width: 140 }}
            value={stage}
            onChange={(e) => {
              setStage(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部阶段</option>
            {Object.entries(STAGE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ width: 140 }}
            value={agentFilter}
            onChange={(e) => {
              setAgentFilter(e.target.value === "" ? "" : Number(e.target.value));
              setPage(1);
            }}
          >
            <option value="">全部员工</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <select
            className="form-control"
            style={{ width: 120 }}
            value={buildingFilter}
            onChange={(e) => {
              setBuildingFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部楼栋</option>
            {buildings.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>

        <table>
          <thead>
            <tr>
              {!isPM && (
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.length === items.length && items.length > 0}
                    onChange={(e) =>
                      setSelectedIds(e.target.checked ? items.map((c) => c.id) : [])
                    }
                  />
                </th>
              )}
              <th>案件编号</th>
              <th>业主</th>
              <th>房号</th>
              <th>欠费金额</th>
              <th>欠费月数</th>
              <th>欠费情况</th>
              <th>阶段</th>
              <th>负责员工</th>
              <th>最后联系</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={isPM ? 10 : 11} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={isPM ? 10 : 11} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无案件数据
                </td>
              </tr>
            )}
            {items.map((c) => {
              const room =
                c.owner.building && c.owner.room
                  ? `${c.owner.building}${c.owner.room}`
                  : (c.owner.building ?? c.owner.room ?? "—");
              const isPaid = c.stage === "paid";
              return (
                <tr
                  key={c.id}
                  style={
                    selectedIds.includes(c.id)
                      ? { background: "var(--color-primary-light)" }
                      : undefined
                  }
                >
                  {!isPM && (
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(c.id)}
                        onChange={() => handleToggleSelect(c.id)}
                      />
                    </td>
                  )}
                  <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                    {c.case_no ?? `CC-${String(c.id).padStart(4, "0")}`}
                  </td>
                  <td>{c.owner.name}</td>
                  <td>{room}</td>
                  <td
                    style={{
                      color: isPaid ? "#057a55" : "#e02424",
                      fontWeight: 600,
                    }}
                  >
                    {c.amount_owed ? `¥${Number(c.amount_owed).toLocaleString()}` : "—"}
                  </td>
                  <td>{c.months_overdue != null ? `${c.months_overdue}个月` : "—"}</td>
                  <td
                    style={{
                      maxWidth: 180,
                      fontSize: 12,
                      color: "var(--color-neutral-600)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                    title={c.notes ?? undefined}
                  >
                    {c.notes ?? <span className="text-muted">—</span>}
                  </td>
                  <td>
                    <span className={STAGE_BADGE_CLASS[c.stage] ?? "ds-badge ds-badge-gray"}>
                      {STAGE_LABELS[c.stage] ?? c.stage}
                    </span>
                  </td>
                  <td>
                    {(() => {
                      const a = agents.find((x) => x.id === c.assigned_to);
                      return a ? (
                        <span>{a.name}</span>
                      ) : c.assigned_to ? (
                        <span>已分配</span>
                      ) : (
                        <span className="text-muted">—</span>
                      );
                    })()}
                  </td>
                  <td>
                    {c.last_contact_at ? (
                      formatLastContact(c.last_contact_at)
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/admin/cases/${c.id}` })}
                    >
                      详情
                    </button>
                    {!isPM && !c.assigned_to && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        onClick={() => {
                          setSelectedIds([c.id]);
                          setAssignModalOpen(true);
                        }}
                      >
                        分配
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="ds-pagination">
          <span className="pagination-info">
            共 {total} 条，第 {page}/{totalPages} 页
          </span>
          <div className="pagination-pages">{paginationButtons}</div>
        </div>
      </div>

      {/* Assign Modal */}
      {assignModalOpen && (
        <div className="modal-overlay" onClick={() => setAssignModalOpen(false)}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">
                <CheckSquare className="inline w-4 h-4 mr-1" />
                分配案件（共 {selectedIds.length} 件）
              </span>
              <button
                type="button"
                className="modal-close"
                onClick={() => setAssignModalOpen(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">
                  选择催收员<span className="req">*</span>
                </label>
                <select
                  className="form-control"
                  value={selectedAgentId ?? ""}
                  onChange={(e) => setSelectedAgentId(Number(e.target.value) || null)}
                >
                  <option value="">请选择</option>
                  {agents
                    .filter((a) =>
                      ["agent_internal", "agent_external"].includes(a.role),
                    )
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}（{a.phone_masked}）
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                onClick={() => {
                  setAssignModalOpen(false);
                  setSelectedAgentId(null);
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                disabled={!selectedAgentId || assigning}
                onClick={handleAssign}
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

function renderPaginationPages(
  page: number,
  totalPages: number,
  setPage: (n: number) => void,
) {
  const pages: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }
  return (
    <>
      {pages.map((p, i) =>
        p === "..." ? (
          <div key={`dot-${i}`} className="page-btn" style={{ cursor: "default", border: "none" }}>
            …
          </div>
        ) : (
          <div
            key={p}
            className={`page-btn${p === page ? " active" : ""}`}
            onClick={() => setPage(p)}
          >
            {p}
          </div>
        ),
      )}
      {page < totalPages && (
        <div className="page-btn" onClick={() => setPage(page + 1)}>
          ›
        </div>
      )}
    </>
  );
}
