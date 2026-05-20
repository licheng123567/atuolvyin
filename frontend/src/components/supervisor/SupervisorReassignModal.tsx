// v0.5.4 — 督导重新分配案件给另一催收员弹窗
// 后端:POST /api/v1/supervisor/cases/{case_id}/reassign
//       body: { target_user_id: int, note?: str }
// 目标催收员选择:输入 user_id(MVP);后续可扩展为内勤催收员下拉(需新增 supervisor-accessible agent 列表端点)
import { useCustomMutation } from "@refinedev/core";
import { Loader2, Users, X } from "lucide-react";
import { useState } from "react";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-base font-semibold">
              重新分配案件 #{caseId}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
            提交后:案件 assigned_to 切换到目标催收员 + 推送通知给新/原催收员 + 时间线写入「重新分配」事件。
          </div>

          {currentAssignedTo && (
            <div className="text-xs text-[var(--color-neutral-500)]">
              当前催收员: user #{currentAssignedTo}
            </div>
          )}

          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
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
            <div className="text-xs text-red-600">
              目标不能与当前催收员相同
            </div>
          )}

          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
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

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-[var(--color-neutral-200)]">
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
        </div>
      </div>
    </div>
  );
}
