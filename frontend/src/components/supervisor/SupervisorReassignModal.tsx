// v0.5.4 — 督导重新分配案件给另一催收员弹窗
// 后端:POST /api/v1/supervisor/cases/{case_id}/reassign
//       body: { target_user_id: int, note?: str }
//
// v0.5.6 — 从中间 Modal 迁移到 RightDrawer(用户反馈:分配时需要持续看到左侧案件列表,
// 中间弹窗挡住了上下文)。这是 RightDrawer 的样板迁移,后续 modal 渐进改,详见
// docs/UI_PATTERNS_MODAL.md。
//
// 目标催收员选择:输入 user_id(MVP);后续可扩展为内勤催收员下拉(需新增
// supervisor-accessible agent 列表端点)。
import { useCustomMutation } from "@refinedev/core";
import { Loader2, Users } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../ui/RightDrawer";

export function SupervisorReassignModal({
  caseId,
  currentAssignedTo,
  onClose,
  onDone,
}: {
  caseId: number;
  currentAssignedTo?: number | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [targetIdStr, setTargetIdStr] = useState("");
  const [note, setNote] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const targetId = Number(targetIdStr);
  const validTarget = targetId > 0 && targetId !== currentAssignedTo;

  const handleSubmit = () => {
    if (!validTarget) return;
    mutate(
      {
        url: `supervisor/cases/${caseId}/reassign`,
        method: "post",
        values: { target_user_id: targetId, note: note.trim() || undefined },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) =>
          alert(
            `重新分配失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="supervisor-reassign"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[var(--color-primary)]" />
          重新分配案件 #{caseId}
        </span>
      }
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!validTarget || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            确认重新分配
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
          提交后:案件 assigned_to 切换到目标催收员 + 推送通知给新/原催收员 + 时间线写入「重新分配」事件。
        </div>

        {currentAssignedTo && (
          <div className="text-xs text-[var(--color-neutral-500)]">
            当前催收员: user #{currentAssignedTo}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            目标催收员 user_id <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            min={1}
            value={targetIdStr}
            onChange={(e) => setTargetIdStr(e.target.value)}
            placeholder="请输入新催收员的 user_id"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
            autoFocus
          />
          {targetId > 0 && targetId === currentAssignedTo && (
            <div className="mt-1 text-xs text-red-600">
              目标不能与当前催收员相同
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            备注(选填)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="如「原催收员请假 / 业主投诉换人」"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
          />
        </div>
      </div>
    </RightDrawer>
  );
}
