// frontend/src/pages/admin/cases/kanban.tsx
import { useCustomMutation, useInvalidate, useList, useGo } from "@refinedev/core";
import { Briefcase, KanbanSquare, List } from "lucide-react";
import { useRef } from "react";
import type { PaginatedResponse } from "../../../types";
import {
  groupByStage,
  STAGE_BORDER_COLORS,
  STAGE_HEADER_COLORS,
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

export function CaseKanbanPage() {
  const go = useGo();
  const invalidate = useInvalidate();
  const { mutate: patchStage } = useCustomMutation();

  // Track which card is currently being dragged
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

    // Find current stage to skip no-op drops
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
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            案件看板
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {items.length} 件
          </span>
        </div>

        {/* List / Kanban toggle */}
        <div className="flex items-center gap-1 border border-[var(--color-neutral-200)] rounded-md overflow-hidden">
          <button
            type="button"
            onClick={() => go({ to: "/admin/cases" })}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)]"
          >
            <List className="w-4 h-4" />
            列表
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
            style={{ background: "var(--color-primary)" }}
          >
            <KanbanSquare className="w-4 h-4" />
            看板
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-[var(--color-neutral-400)]">
          加载中…
        </div>
      )}

      {!isLoading && (
        <div className="grid grid-cols-6 gap-4 overflow-x-auto">
          {STAGES.map((stage) => {
            const headerColor = STAGE_HEADER_COLORS[stage];
            const isPaid = stage === "paid";
            return (
              <div
                key={stage}
                className="flex flex-col min-w-[230px]"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(stage, e)}
              >
                {/* Column header — semantic background per stage */}
                <div
                  className="flex items-center justify-between font-semibold text-[13px] rounded-t-lg"
                  style={{
                    padding: "10px 14px",
                    background: headerColor.headerBg,
                    color: headerColor.headerText,
                  }}
                >
                  <span>{STAGE_LABELS[stage]}</span>
                  <span
                    className="text-[11px] font-bold rounded-full"
                    style={{
                      background: headerColor.badgeBg,
                      color: headerColor.badgeText,
                      padding: "2px 8px",
                      minWidth: 22,
                      textAlign: "center",
                    }}
                  >
                    {groups[stage].length}
                  </span>
                </div>

                {/* Column body — light gray background */}
                <div
                  className="rounded-b-lg p-2.5 flex flex-col gap-2 flex-1 min-h-[400px]"
                  style={{ background: "#f3f4f6" }}
                >
                  {groups[stage].map((c) => (
                    <div
                      key={c.id}
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
                      className="bg-white cursor-move hover:shadow-md transition-shadow select-none"
                      style={{
                        padding: 12,
                        borderRadius: 6,
                        boxShadow: "0 1px 3px rgba(0,0,0,.08)",
                        borderLeft: `3px solid ${STAGE_BORDER_COLORS[stage]}`,
                      }}
                    >
                      <div
                        className="truncate"
                        style={{
                          fontWeight: 600,
                          fontSize: 13.5,
                          color: "#111827",
                        }}
                      >
                        {c.owner.name}
                      </div>
                      {(c.owner.building || c.owner.room) && (
                        <div
                          className="truncate"
                          style={{
                            fontSize: 12,
                            color: "#6b7280",
                            marginTop: 2,
                          }}
                        >
                          {[c.owner.building, c.owner.room]
                            .filter(Boolean)
                            .join("")}
                        </div>
                      )}
                      {c.amount_owed != null && (
                        <div
                          style={{
                            fontWeight: 700,
                            fontSize: 14,
                            marginTop: 6,
                            color: isPaid ? "#057a55" : "#e02424",
                          }}
                        >
                          ¥{c.amount_owed}
                          {isPaid ? " ✓" : ""}
                        </div>
                      )}
                      {c.months_overdue != null && (
                        <div
                          style={{
                            fontSize: 11.5,
                            color: "#9ca3af",
                            marginTop: 4,
                          }}
                        >
                          {c.months_overdue}个月欠费
                        </div>
                      )}
                    </div>
                  ))}

                  {groups[stage].length === 0 && (
                    <div className="flex-1 flex items-center justify-center text-xs text-[var(--color-neutral-300)] border-2 border-dashed border-[var(--color-neutral-200)] rounded-md min-h-[80px]">
                      拖拽卡片到此处
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
