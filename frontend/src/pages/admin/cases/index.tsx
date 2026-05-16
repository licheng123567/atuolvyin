// 1:1 还原 ui/admin.html#a-cases CRM 案件列表
import { useCreate, useCustom, useGetIdentity, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { CheckSquare, Download, KanbanSquare, List, MessageSquarePlus, Plus, Search, UserCheck } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FollowUpNoteModal } from "../../../components/case/FollowUpNoteModal";
import { SearchableSelect } from "../../../components/ui/SearchableSelect";
import { exportToCsv } from "../../../lib/csv";
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
  provider_id?: number | null;
  provider_name?: string | null;
}

interface ProjectOption {
  id: number;
  name: string;
}

interface ProviderOption {
  provider_id: number;
  provider_name: string;
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
  const providerIdParam = searchParams.get("provider_id");
  const providerIdFilter = providerIdParam ? Number(providerIdParam) : null;
  const { data: identity } = useGetIdentity<AuthUser>();
  const isPM = identity?.role === "project_manager";

  const [keyword, setKeyword] = useState(searchParams.get("keyword") ?? "");
  const [stage, setStage] = useState("");
  const [agentFilter, setAgentFilter] = useState<number | "">("");
  const [buildingFilter, setBuildingFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  // v1.8.0 — 列表行「记录跟进」快捷入口
  const [followUpCase, setFollowUpCase] = useState<{ id: number; ownerName: string } | null>(null);
  const PAGE_SIZE = 12;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "keyword", operator: "eq", value: keyword });
  if (stage) filters.push({ field: "stage", operator: "eq", value: stage });
  if (projectIdFilter !== null) {
    filters.push({ field: "project_id", operator: "eq", value: projectIdFilter });
  }
  if (providerIdFilter !== null) {
    filters.push({ field: "provider_id", operator: "eq", value: providerIdFilter });
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

  // 项目下拉数据（始终拉，供过滤器使用）
  const { query: projectQuery } = useList<ProjectOption>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const projectsRaw = projectQuery.data?.data;
  const allProjects: ProjectOption[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectOption>)?.items ??
    (projectsRaw as ProjectOption[] | undefined) ??
    [];
  const currentProject = allProjects.find((p) => p.id === projectIdFilter);

  // v1.5.6 — 服务商下拉（用于按合作服务商过滤）
  const { query: providerQuery } = useList<ProviderOption>({
    resource: "admin/providers",
    pagination: { currentPage: 1, pageSize: 50 },
  });
  const providersRaw = providerQuery.data?.data;
  const allProviders: ProviderOption[] =
    (providersRaw as unknown as PaginatedResponse<ProviderOption>)?.items ??
    (providersRaw as ProviderOption[] | undefined) ??
    [];

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
  // v1.5.6 — 物业 admin 分配给 agent 角色（内部/外部由 work_mode 区分，已收敛到单一角色）
  const agentsAll = allAgents.filter((a) => a.role === "agent");
  const agents = agentsAll;
  // For assignment, all agents with the "agent" role are candidates.
  // TODO: if work_mode is exposed by /admin/users, filter to work_mode=internal for admin-side assignment
  const internalAgents = allAgents.filter((a) => a.role === "agent");

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
            {providerIdFilter !== null && (
              <>
                <span style={{ marginLeft: 12, fontSize: 12, color: "var(--color-neutral-500)" }}>
                  · 仅显示服务商 #{providerIdFilter} 的案件
                </span>
                <button
                  type="button"
                  onClick={() => {
                    searchParams.delete("provider_id");
                    setSearchParams(searchParams);
                    setPage(1);
                  }}
                  style={{
                    marginLeft: 8,
                    fontSize: 12,
                    color: "var(--color-primary)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  ← 清除
                </button>
              </>
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
          <button
            type="button"
            onClick={() => {
              exportToCsv(
                `cases-${new Date().toISOString().slice(0, 10)}.csv`,
                [
                  { key: "id", label: "案件ID" },
                  { key: "owner_name", label: "业主" },
                  { key: "phone_masked", label: "手机（掩码）" },
                  { key: "building", label: "楼栋" },
                  { key: "room", label: "房号" },
                  { key: "stage", label: "阶段" },
                  { key: "amount_owed", label: "欠费金额" },
                  { key: "months_overdue", label: "欠费月数" },
                  { key: "assigned_to", label: "经办员工ID" },
                  { key: "provider_name", label: "服务商" },
                  { key: "last_contact_at", label: "上次联系" },
                ],
                items.map((c) => ({
                  id: c.id,
                  owner_name: c.owner.name,
                  phone_masked: c.owner.phone_masked,
                  building: c.owner.building ?? "",
                  room: c.owner.room ?? "",
                  stage: STAGE_LABELS[c.stage] ?? c.stage,
                  amount_owed: c.amount_owed ?? "",
                  months_overdue: c.months_overdue ?? "",
                  assigned_to: c.assigned_to ?? "",
                  provider_name: c.provider_name ?? "",
                  last_contact_at: c.last_contact_at ?? "",
                })),
              );
            }}
            disabled={items.length === 0}
            className="ds-btn ds-btn-secondary"
            title="导出当前页面的案件为 CSV"
          >
            <Download className="w-3.5 h-3.5" />
            导出 CSV
          </button>
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
          <SearchableSelect
            style={{ width: 200 }}
            value={projectIdFilter ?? ""}
            placeholder="全部项目"
            onChange={(v) => {
              if (v === "") searchParams.delete("project_id");
              else searchParams.set("project_id", String(v));
              setSearchParams(searchParams);
              setPage(1);
            }}
            options={allProjects.map((p) => ({ value: p.id, label: p.name }))}
          />
          <SearchableSelect
            style={{ width: 180 }}
            value={providerIdFilter ?? ""}
            placeholder="全部服务商"
            onChange={(v) => {
              if (v === "") searchParams.delete("provider_id");
              else searchParams.set("provider_id", String(v));
              setSearchParams(searchParams);
              setPage(1);
            }}
            options={allProviders.map((p) => ({
              value: p.provider_id,
              label: p.provider_name,
            }))}
          />
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
          <SearchableSelect
            style={{ width: 160 }}
            value={agentFilter}
            placeholder="全部员工"
            onChange={(v) => {
              setAgentFilter(v === "" ? "" : Number(v));
              setPage(1);
            }}
            options={agents.map((a) => ({
              value: a.id,
              label: a.name,
              subtitle: a.phone_masked,
            }))}
          />
          <SearchableSelect
            style={{ width: 130 }}
            value={buildingFilter}
            placeholder="全部楼栋"
            onChange={(v) => {
              setBuildingFilter(String(v));
              setPage(1);
            }}
            options={buildings.map((b) => ({ value: b, label: b }))}
          />
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
              <th>服务商</th>
              <th>负责员工</th>
              <th>最后联系</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={isPM ? 11 : 12} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={isPM ? 11 : 12} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
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
                    {c.provider_name ? (
                      <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
                        {c.provider_name}
                      </span>
                    ) : (
                      <span className="ds-badge ds-badge-gray" style={{ fontSize: 11 }}>
                        物业自办
                      </span>
                    )}
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
                    {!isPM && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        onClick={() => setFollowUpCase({ id: c.id, ownerName: c.owner.name })}
                        title="无需进入详情页，直接写本次跟进备注"
                      >
                        <MessageSquarePlus className="w-3.5 h-3.5" />
                        记录跟进
                      </button>
                    )}
                    {!isPM && !c.assigned_to && !c.provider_id && (
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
                    {!isPM && !c.assigned_to && c.provider_id && (
                      <span
                        className="text-muted"
                        style={{ fontSize: 11, marginLeft: 4 }}
                        title="本案件归外包项目，由服务商内部决定坐席"
                      >
                        服务商待分配
                      </span>
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
                  <option value="">请选择内部催收员</option>
                  {internalAgents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}（{a.phone_masked}）
                    </option>
                  ))}
                </select>
                <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
                  外包项目的案件由服务商内部分配，本入口仅可分给物业内部催收员。
                </div>
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

      {/* v1.8.0 — 列表行「记录跟进」Modal */}
      {followUpCase && (
        <FollowUpNoteModal
          caseId={followUpCase.id}
          ownerName={followUpCase.ownerName}
          endpoint={`admin/cases/${followUpCase.id}/stage`}
          invalidateResource="admin/cases"
          onClose={() => setFollowUpCase(null)}
        />
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
