// frontend/src/pages/admin/cases/kanban.tsx
import { useCustomMutation, useInvalidate, useList, useGo } from "@refinedev/core";
import { Briefcase, KanbanSquare, List } from "lucide-react";
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

export function CaseKanbanPage() {
  const go = useGo();
  const invalidate = useInvalidate();
  const { mutate: patchStage } = useCustomMutation();

  // Track which card is currently being dragged
  const draggingId = useRef<number | null>(null);

  const { data: rawData, isLoading } = useList<CaseItem>({
    resource: "admin/cases",
    pagination: { currentPage: 1, pageSize: 200 },
  });

  const items: CaseItem[] =
    (rawData?.data as unknown as PaginatedResponse<CaseItem>)?.items ??
    (rawData?.data as CaseItem[] | undefined) ??
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
        <div className="grid grid-cols-6 gap-3 overflow-x-auto">
          {STAGES.map((stage) => (
            <div
              key={stage}
              className="bg-[var(--color-neutral-50)] rounded-lg p-3 min-h-[400px] flex flex-col"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => handleDrop(stage, e)}
            >
              {/* Column header */}
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold text-sm text-[var(--color-neutral-700)]">
                  {STAGE_LABELS[stage]}
                </h4>
                <span className="text-xs font-medium text-[var(--color-neutral-400)] bg-[var(--color-neutral-100)] px-1.5 py-0.5 rounded-full">
                  {groups[stage].length}
                </span>
              </div>

              {/* Cards */}
              <div className="flex flex-col gap-2 flex-1">
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
                    className="bg-white rounded-md p-3 shadow-sm cursor-move text-sm border-l-4 hover:shadow-md transition-shadow select-none"
                    style={{
                      borderLeftColor: STAGE_BORDER_COLORS[stage],
                    }}
                  >
                    <div className="font-medium text-[var(--color-neutral-900)] truncate">
                      {c.owner.name}
                    </div>
                    {(c.owner.building || c.owner.room) && (
                      <div className="text-xs text-[var(--color-neutral-500)] mt-0.5 truncate">
                        {[c.owner.building, c.owner.room].filter(Boolean).join(" ")}
                      </div>
                    )}
                    <div className="text-xs text-[var(--color-neutral-500)] mt-1 flex items-center gap-1">
                      {c.amount_owed != null && (
                        <span className="font-medium text-[var(--color-neutral-700)]">
                          ¥{c.amount_owed}
                        </span>
                      )}
                      {c.amount_owed != null && c.months_overdue != null && (
                        <span className="text-[var(--color-neutral-300)]">·</span>
                      )}
                      {c.months_overdue != null && (
                        <span>{c.months_overdue}个月</span>
                      )}
                    </div>
                  </div>
                ))}

                {groups[stage].length === 0 && (
                  <div className="flex-1 flex items-center justify-center text-xs text-[var(--color-neutral-300)] border-2 border-dashed border-[var(--color-neutral-200)] rounded-md min-h-[80px]">
                    拖拽卡片到此处
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
