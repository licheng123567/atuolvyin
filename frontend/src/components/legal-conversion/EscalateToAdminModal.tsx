// v0.5.4 — 督导「上报 admin」转法务申请弹窗
// 后端:POST /api/v1/legal-conversion-requests/{id}/escalate-to-admin
// body: { reason: string }(上报理由,必填)
import { useCustomMutation } from "@refinedev/core";
import { Loader2, X } from "lucide-react";
import { useState } from "react";

export function EscalateToAdminModal({
  requestId,
  onClose,
  onEscalated,
}: {
  requestId: number;
  onClose: () => void;
  onEscalated: () => void;
}) {
  const [reason, setReason] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    const trimmed = reason.trim();
    if (!trimmed) return;
    mutate(
      {
        url: `legal-conversion-requests/${requestId}/escalate-to-admin`,
        method: "post",
        values: { reason: trimmed },
      },
      {
        onSuccess: () => onEscalated(),
        onError: (err) =>
          alert(
            `上报失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <h2 className="text-base font-semibold">
            上报 admin 审批 — 转法务申请 #{requestId}
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
          <div className="text-xs text-[var(--color-neutral-600)] bg-amber-50 border border-amber-200 rounded p-2">
            上报后此申请将进入 admin 待审批列表,你不再能批/驳此申请。请说明为何需 admin 决定(如:超出督导决断范围 / 金额过大 / 业主投诉到公司)。
          </div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
            上报理由 <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            placeholder="必填,说明为何需 admin 决定"
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
            disabled={!reason.trim() || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            上报 admin
          </button>
        </div>
      </div>
    </div>
  );
}
