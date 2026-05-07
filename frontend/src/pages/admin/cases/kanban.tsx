// 1:1 还原 ui/admin.html#a-kanban 案件看板
import { useCustomMutation, useInvalidate, useList, useGo } from "@refinedev/core";
import { KanbanSquare, List } from "lucide-react";
import { useRef } from "react";
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
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  status: string;
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

  const draggingId = useRef<number | null>(null);

  const { query, result } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: 1, pageSize: 200 },
  });
  const isLoading = query.isLoading;

  const rawData = query.data;
  const items: CaseItem[] =
    (rawData?.data as unknown as PaginatedResponse<CaseItem>)?.items ??
    (result.data as CaseItem[] | undefined) ??
    [];

  const groups = groupByStage(items);

  function handleDrop(newStage: Stage, e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
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
          <h1 className="page-title">案件看板</h1>
          <div className="page-subtitle">共 {items.length} 件案件 · 拖拽卡片切换阶段</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" disabled>
            按员工筛选
          </button>
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
                      draggable
                      onDragStart={(e) => {
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
                      拖拽到此处
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
