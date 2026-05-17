// 1:1 还原 ui/admin.html#a-pool 公海管理
// v1.6.5 — 服务端分页 + debounce 关键字搜索
import {
  useCustomMutation,
  useGo,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { useState } from "react";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import type { PaginatedResponse } from "../../../types";

const PAGE_SIZE = 20;

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
  release_reason?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
}

interface UserItem {
  id: number;
  name: string;
  role: string;
}

const AGENT_QUOTA = 20; // 单个坐席私海上限（演示值）

function formatJoinedAgo(iso: string): string {
  const d = new Date(iso);
  const day = Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (day === 0) return "今天";
  if (day === 1) return "1天前";
  if (day < 30) return `${day}天前`;
  return d.toISOString().slice(0, 10);
}

function priorityBadge(score: number): { className: string; label: string } {
  if (score >= 80) return { className: "ds-badge ds-badge-red", label: `${score}分` };
  if (score >= 60)
    return { className: "ds-badge ds-badge-orange", label: `${score}分` };
  if (score >= 40) return { className: "ds-badge ds-badge-blue", label: `${score}分` };
  return { className: "ds-badge ds-badge-gray", label: `${score}分` };
}

interface ProjectOption {
  id: number;
  name: string;
}

export function AdminPoolPage() {
  const [page, setPage] = useState(1);
  const [assignFor, setAssignFor] = useState<number | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [overdueFilter, setOverdueFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState<number | "">("");
  const [sortBy, setSortBy] = useState<"priority" | "amount" | "joined">("priority");
  const debouncedKw = useDebouncedValue(keyword, 300);
  const invalidate = useInvalidate();
  const go = useGo();

  const filters: Array<{ field: string; operator: "eq" | "contains"; value: string | number }> = [
    { field: "pool_type", operator: "eq", value: "public" },
  ];
  if (projectFilter !== "") {
    filters.push({ field: "project_id", operator: "eq", value: projectFilter });
  }
  if (debouncedKw.trim()) {
    filters.push({ field: "keyword", operator: "contains", value: debouncedKw.trim() });
  }

  const { query: casesQuery } = useList<CaseItem>({
    resource: "admin/cases",
    filters,
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const { query: projectsQuery } = useList<ProjectOption>({
    resource: "admin/projects",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const projectsRaw = projectsQuery.data?.data;
  const projects: ProjectOption[] =
    (projectsRaw as unknown as PaginatedResponse<ProjectOption>)?.items ??
    (projectsRaw as ProjectOption[] | undefined) ??
    [];

  const rawCases = casesQuery.data?.data;
  const paginated = rawCases as unknown as PaginatedResponse<CaseItem> | undefined;
  const allCases: CaseItem[] =
    paginated?.items ?? (rawCases as CaseItem[] | undefined) ?? [];
  const total = paginated?.total ?? allCases.length;

  // v1.5.6 — 双层公海：物业公海仅显示自营项目（无 provider）+ 无项目的 case
  // 外包项目的公海归服务商管，物业 admin 不在此分配
  // v1.6.5 — 关键字搜索 / 项目筛选已下沉后端；overdue 范围筛选仍在前端做（仅作用于当前页）
  const outsourcedCount = allCases.filter((c) => c.provider_id != null).length;
  let cases = allCases.filter((c) => {
    if (c.provider_id != null) return false;
    const m = c.months_overdue ?? 0;
    if (overdueFilter === ">12" && m <= 12) return false;
    if (overdueFilter === "6-12" && (m < 6 || m > 12)) return false;
    if (overdueFilter === "3-6" && (m < 3 || m > 6)) return false;
    return true;
  });

  // 排序
  cases = [...cases].sort((a, b) => {
    if (sortBy === "amount")
      return parseFloat(b.amount_owed ?? "0") - parseFloat(a.amount_owed ?? "0");
    if (sortBy === "joined")
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    return (
      b.priority_score - a.priority_score ||
      parseFloat(b.amount_owed ?? "0") - parseFloat(a.amount_owed ?? "0")
    );
  });

  const isLoading = casesQuery.isLoading;

  // 员工列表（用于私海概览 + 分配 modal）
  const { query: agentsQuery, result: agentsResult } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const rawAgents = agentsQuery.data?.data;
  const allUsers: UserItem[] =
    (rawAgents as unknown as PaginatedResponse<UserItem>)?.items ??
    (agentsResult.data as UserItem[] | undefined) ??
    [];
  // v1.5.6 — 物业 admin 分配给 agent 角色（内部/外部由 work_mode 区分，已统一到单一 agent 角色）
  // TODO: once /admin/users exposes work_mode, filter to work_mode=internal for property-side assignment
  const agents = allUsers.filter((u) => u.role === "agent");

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
        onError: () => alert("分配失败，请重试"),
      },
    );
  };

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">物业公海</h1>
          <div className="page-subtitle">
            自营项目待分配：{cases.length} 个案件
            {outsourcedCount > 0 && (
              <span style={{ marginLeft: 12, color: "#9ca3af", fontSize: 12 }}>
                · 另有 {outsourcedCount} 个外包案件由服务商管理（不在此显示）
              </span>
            )}
          </div>
        </div>
        <button type="button" className="ds-btn ds-btn-primary" disabled>
          批量分配
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 280px",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* Left: cases table */}
        <div className="table-wrap">
          <div className="table-toolbar">
            <SearchInput
              value={keyword}
              onChange={(v) => { setKeyword(v); setPage(1); }}
              placeholder="搜索业主 / 房号"
              width={220}
            />
            <select
              className="form-control"
              style={{ width: 160 }}
              value={projectFilter}
              onChange={(e) =>
                setProjectFilter(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
            >
              <option value="">全部项目</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              className="form-control"
              style={{ width: 140 }}
              value={overdueFilter}
              onChange={(e) => setOverdueFilter(e.target.value)}
            >
              <option value="">全部欠费等级</option>
              <option value=">12">&gt; 12 个月</option>
              <option value="6-12">6-12 个月</option>
              <option value="3-6">3-6 个月</option>
            </select>
            <select
              className="form-control"
              style={{ width: 130 }}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            >
              <option value="priority">优先级排序</option>
              <option value="amount">欠费金额↓</option>
              <option value="joined">入池时间↑</option>
            </select>
          </div>
          <table>
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input type="checkbox" disabled />
                </th>
                <th>业主</th>
                <th>房号</th>
                <th>欠费金额</th>
                <th>欠费月数</th>
                <th>进池原因</th>
                <th>优先级</th>
                <th>入池时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                    加载中…
                  </td>
                </tr>
              )}
              {!isLoading && cases.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                    公海无案件
                  </td>
                </tr>
              )}
              {cases.map((c) => {
                const priority = priorityBadge(c.priority_score);
                const room =
                  c.owner.building && c.owner.room
                    ? `${c.owner.building}${c.owner.room}`
                    : c.owner.building ?? c.owner.room ?? "—";
                return (
                  <tr key={c.id}>
                    <td>
                      <input type="checkbox" />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        style={{ padding: 0 }}
                        onClick={() => go({ to: `/admin/cases/${c.id}` })}
                      >
                        {c.owner.name}
                      </button>
                    </td>
                    <td>{room}</td>
                    <td style={{ color: "#e02424", fontWeight: 600 }}>
                      {c.amount_owed
                        ? `¥${Number(c.amount_owed).toLocaleString()}`
                        : "—"}
                    </td>
                    <td>
                      {c.months_overdue != null ? `${c.months_overdue}个月` : "—"}
                    </td>
                    <td className="text-muted">{c.release_reason ?? "超时未跟进"}</td>
                    <td>
                      <span className={priority.className}>{priority.label}</span>
                    </td>
                    <td>{formatJoinedAgo(c.created_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="ds-btn ds-btn-primary ds-btn-sm"
                        onClick={() => setAssignFor(c.id)}
                      >
                        分配
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <PaginationBar
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
          />
        </div>

        {/* Right: 员工私海概览 */}
        <div className="ds-card">
          <div className="card-header">
            <span className="card-title">员工私海概览</span>
          </div>
          <div
            className="card-body"
            style={{ display: "flex", flexDirection: "column", gap: 12 }}
          >
            {agents.length === 0 && (
              <div style={{ fontSize: 13, color: "#9ca3af" }}>暂无催收员</div>
            )}
            {agents.map((a) => {
              // TODO(v1.1) 真实 case_count 字段
              const count = 0;
              const pct = (count / AGENT_QUOTA) * 100;
              const over = count > AGENT_QUOTA;
              return (
                <div key={a.id} className="agent-load">
                  <div style={{ width: 60, fontSize: 13, fontWeight: 500 }}>
                    {a.name}
                  </div>
                  <div className="load-bar-wrap">
                    <div
                      className={`load-bar${over ? " over" : ""}`}
                      style={{ width: `${Math.min(pct, 110)}%` }}
                    />
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      color: over ? "#e02424" : "#6b7280",
                      width: 50,
                      textAlign: "right",
                    }}
                  >
                    {count}/{AGENT_QUOTA}
                    {over ? " ⚠" : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Assign modal */}
      {assignFor !== null && (
        <div
          className="modal-overlay"
          onClick={() => {
            setAssignFor(null);
            setSelectedAgent(null);
          }}
        >
          <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">分配案件</span>
              <button
                type="button"
                className="modal-close"
                onClick={() => {
                  setAssignFor(null);
                  setSelectedAgent(null);
                }}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">
                  选择催收员<span className="req">*</span>
                </label>
                {agents.length === 0 ? (
                  <p style={{ fontSize: 13, color: "#9ca3af" }}>暂无可用催收员</p>
                ) : (
                  <select
                    className="form-control"
                    value={selectedAgent ?? ""}
                    onChange={(e) =>
                      setSelectedAgent(Number(e.target.value) || null)
                    }
                  >
                    <option value="">— 选择员工 —</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                        {/* TODO: show work_mode (internal/external) once /admin/users exposes work_mode */}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                onClick={() => {
                  setAssignFor(null);
                  setSelectedAgent(null);
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                onClick={handleAssign}
                disabled={selectedAgent === null}
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
