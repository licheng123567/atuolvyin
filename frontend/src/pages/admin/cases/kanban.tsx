// 1:1 还原 ui/admin.html#a-kanban 案件看板
import type { CrudFilter } from "@refinedev/core";
import {
  useCustomMutation,
  useGetIdentity,
  useGo,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { KanbanSquare, List } from "lucide-react";
import { useRef } from "react";
import { useSearchParams } from "react-router-dom";
import type { AuthUser } from "../../../providers/auth-provider";
import type { PaginatedResponse } from "../../../types";
import {
  groupByStage,
  STAGE_BORDER_COLORS,
  STAGE_LABELS,
  STAGES,
  type Stage,
} from "./kanban-helpers";

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
}

interface ProjectOption {
  id: number;
  name: string;
}

const COL_CLASS: Record<Stage, string> = {
  new: "kanban-col col-pending",
  in_progress: "kanban-col col-follow",
  promised: "kanban-col col-promise",
  paid: "kanban-col col-paid",
  escalated: "kanban-col col-escalate",
  closed: "kanban-col col-closed",
};

const STAGE_BADGE_CLASS: Record<Stage, string> = {
  new: "ds-badge ds-badge-gray",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-orange",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

export function CaseKanbanPage() {
  const go = useGo();
  const invalidate = useInvalidate();
  const { mutate: patchStage } = useCustomMutation();
  const { data: identity } = useGetIdentity<AuthUser>();
  const isPM =
    identity?.role === "project_manager_property" ||
    identity?.role === "project_manager_provider";

  const [searchParams, setSearchParams] = useSearchParams();
  const projectIdParam = searchParams.get("project_id");
  const projectIdFilter = projectIdParam ? Number(projectIdParam) : null;

  const draggingId = useRef<number | null>(null);

  const filters: CrudFilter[] = [];
  if (projectIdFilter !== null) {
    filters.push({ field: "project_id", operator: "eq", value: projectIdFilter });
  }

  const { query, result } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: 1, pageSize: 200 },
    filters,
  });
  const isLoading = query.isLoading;

  const rawData = query.data;
  const items: CaseItem[] =
    (rawData?.data as unknown as PaginatedResponse<CaseItem>)?.items ??
    (result.data as CaseItem[] | undefined) ??
    [];

  // 项目下拉（用于筛选）
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

  const groups = groupByStage(items);

  function handleDrop(newStage: Stage, e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (isPM) return;
    const idStr = e.dataTransfer.getData("text/plain");
    const id = Number(idStr);
    if (!id) return;
    const currentCase = items.find((c) => c.id === id);
    if (!currentCase || currentCase.stage === newStage) return;

    patchStage(
      {
        url: `admin/cases/${id}/stage`,
        method: "patch",
        values: { stage: newStage },
      },
      {
        onSuccess: () => {
          void invalidate({ resource: "admin/cases", invalidates: ["list"] });
        },
      },
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {currentProject ? `${currentProject.name} · 案件看板` : "案件看板"}
          </h1>
          <div className="page-subtitle">
            共 {items.length} 件案件
            {isPM ? " · 只读视图" : " · 拖拽卡片切换阶段"}
            {projectIdFilter !== null && (
              <button
                type="button"
                onClick={() => {
                  searchParams.delete("project_id");
                  setSearchParams(searchParams);
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
          <select
            className="form-control"
            style={{ width: 180 }}
            value={projectIdParam ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "") {
                searchParams.delete("project_id");
              } else {
                searchParams.set("project_id", val);
              }
              setSearchParams(searchParams);
            }}
          >
            <option value="">全部项目</option>
            {allProjects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {/* List / Kanban toggle */}
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
              onClick={() => go({ to: "/admin/cases" })}
              className="ds-btn ds-btn-secondary ds-btn-sm"
              style={{ border: "none", borderRadius: 0 }}
            >
              <List className="w-3.5 h-3.5" />
              列表
            </button>
            <button
              type="button"
              className="ds-btn ds-btn-primary ds-btn-sm"
              style={{ borderRadius: 0 }}
            >
              <KanbanSquare className="w-3.5 h-3.5" />
              看板
            </button>
          </div>
        </div>
      </div>

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48, color: "#9ca3af" }}>
          加载中…
        </div>
      )}

      {!isLoading && (
        <div className="kanban-board">
          {STAGES.map((stage) => {
            const isPaid = stage === "paid";
            return (
              <div
                key={stage}
                className={COL_CLASS[stage]}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(stage, e)}
              >
                <div className="kanban-col-header">
                  <span>{STAGE_LABELS[stage]}</span>
                  <span className={STAGE_BADGE_CLASS[stage]}>
                    {groups[stage].length}
                  </span>
                </div>
                <div className="kanban-col-body">
                  {groups[stage].map((c) => (
                    <div
                      key={c.id}
                      className="kanban-card"
                      draggable={!isPM}
                      onDragStart={(e) => {
                        if (isPM) {
                          e.preventDefault();
                          return;
                        }
                        draggingId.current = c.id;
                        e.dataTransfer.setData("text/plain", String(c.id));
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onDragEnd={() => {
                        draggingId.current = null;
                      }}
                      onClick={() => go({ to: `/admin/cases/${c.id}` })}
                      style={{
                        borderLeftColor: STAGE_BORDER_COLORS[stage],
                        opacity: stage === "closed" ? 0.7 : 1,
                        cursor: isPM ? "pointer" : "grab",
                      }}
                    >
                      <div className="owner">{c.owner.name}</div>
                      {(c.owner.building || c.owner.room) && (
                        <div className="unit">
                          {[c.owner.building, c.owner.room].filter(Boolean).join("")}
                        </div>
                      )}
                      {c.amount_owed != null && (
                        <div
                          className="amount"
                          style={isPaid ? { color: "#057a55" } : undefined}
                        >
                          ¥{Number(c.amount_owed).toLocaleString()}
                          {isPaid ? " ✓" : ""}
                        </div>
                      )}
                      <div className="meta">
                        {c.months_overdue != null
                          ? `${c.months_overdue}个月欠费`
                          : "—"}
                        {c.assigned_to ? " · 已分配" : " · 未分配"}
                      </div>
                    </div>
                  ))}
                  {groups[stage].length === 0 && (
                    <div
                      style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        color: "#cbd5e1",
                        border: "2px dashed #e5e7eb",
                        borderRadius: 6,
                        minHeight: 80,
                      }}
                    >
                      {isPM ? "暂无案件" : "拖拽到此处"}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
