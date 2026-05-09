// v1.6.8 — 法务转化申请「驳回」弹窗
import { useCustomMutation } from "@refinedev/core";
import { Loader2, X } from "lucide-react";
import { useState } from "react";

export function RejectRequestModal({
  requestId,
  onClose,
  onRejected,
}: {
  requestId: number;
  onClose: () => void;
  onRejected: () => void;
}) {
  const [reason, setReason] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    const trimmed = reason.trim();
    if (!trimmed) return;
    mutate(
      {
        url: `legal-conversion-requests/${requestId}/reject`,
        method: "post",
        values: { reason: trimmed },
      },
      {
        onSuccess: () => onRejected(),
        onError: (err) => {
          alert(`驳回失败：${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <h2 className="text-base font-semibold">驳回转法务申请 #{requestId}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
            驳回理由 <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            placeholder="必填，向催收员说明为何不批准本次申请（如：催收次数不够 / 业主已有承诺方案 / 应继续协商）"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            autoFocus
          />
          <div className="text-xs text-[var(--color-neutral-500)]">
            驳回后催收员可在案件详情看到反馈，并继续电话跟进。
          </div>
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
            disabled={!reason.trim() || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            提交驳回
          </button>
        </div>
      </div>
    </div>
  );
}
