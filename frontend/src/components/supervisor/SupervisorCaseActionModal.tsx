// v0.5.4 — 督导对案件的快速动作弹窗(催回访 / 催办 / 介入处理)
// 统一通过 useCustomMutation 调对应 supervisor/cases/{id}/{action} 端点
import { useCustomMutation } from "@refinedev/core";
import { Loader2, X } from "lucide-react";
import { useState } from "react";

export type SupervisorActionType = "remind_callback" | "urge" | "intervene";

const ACTION_META: Record<
  SupervisorActionType,
  {
    title: string;
    endpoint: string;
    noteRequired: boolean;
    notePlaceholder: string;
    submitLabel: string;
    submitClass: string;
  }
> = {
  remind_callback: {
    title: "催回访",
    endpoint: "remind-callback",
    noteRequired: false,
    notePlaceholder:
      "选填:具体备注(如「业主下午 3 点有空,请回拨」)",
    submitLabel: "发送催回访通知",
    submitClass: "bg-blue-600 hover:bg-blue-700",
  },
  urge: {
    title: "催办",
    endpoint: "urge",
    noteRequired: false,
    notePlaceholder: "选填:催办备注(如「已停滞 14 天,请尽快推进」)",
    submitLabel: "发送催办通知",
    submitClass: "bg-amber-600 hover:bg-amber-700",
  },
  intervene: {
    title: "介入处理",
    endpoint: "intervene",
    noteRequired: true,
    notePlaceholder: "必填:介入原因(如「业主投诉到公司,督导接管」)",
    submitLabel: "确认介入",
    submitClass: "bg-red-600 hover:bg-red-700",
  },
};

export function SupervisorCaseActionModal({
  caseId,
  type,
  onClose,
  onDone,
}: {
  caseId: number;
  type: SupervisorActionType;
  onClose: () => void;
  onDone: () => void;
}) {
  const meta = ACTION_META[type];
  const [note, setNote] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const noteTrim = note.trim();
  const canSubmit = !meta.noteRequired || noteTrim.length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    mutate(
      {
        url: `supervisor/cases/${caseId}/${meta.endpoint}`,
        method: "post",
        values: { note: noteTrim || undefined },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) =>
          alert(
            `${meta.title}失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <h2 className="text-base font-semibold">
            {meta.title} — 案件 #{caseId}
          </h2>
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
            提交后会写入案件时间线 + 推送通知给当前催收员。
          </div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
            备注{meta.noteRequired && <span className="text-red-500"> *</span>}
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            placeholder={meta.notePlaceholder}
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            autoFocus
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
            disabled={!canSubmit || mutation.isPending}
            className={`px-4 py-1.5 text-sm rounded text-white disabled:opacity-50 flex items-center gap-1.5 ${meta.submitClass}`}
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {meta.submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
