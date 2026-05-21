// v0.6.0 — 督导「直接移交法务」弹窗(无催收员申请时使用)
//
// 与「催收员申请 → 督导审批」流路径互斥 — 后端 POST
// /supervisor/cases/{id}/transfer-legal 会校验:若已有 pending 申请,返回 409。
// 提交 case.stage → 'legal' + 写 audit + 通知原催收员。
import { useCustomMutation } from "@refinedev/core";
import { Loader2, Scale, X } from "lucide-react";
import { useState } from "react";

interface Props {
  caseId: number;
  caseLabel?: string;  // 业主名 · #caseId
  onClose: () => void;
  onDone: () => void;
}

export function TransferLegalDirectModal({ caseId, caseLabel, onClose, onDone }: Props) {
  const [reason, setReason] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    const trimmed = reason.trim();
    if (!trimmed) return;
    mutate(
      {
        url: `supervisor/cases/${caseId}/transfer-legal`,
        method: "post",
        values: { reason: trimmed },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => {
          const msg = (err as { message?: string }).message ?? "请重试";
          alert(`移交失败:${msg}`);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Scale className="w-5 h-5 text-violet-600" />
            直接移交法务{caseLabel ? ` · ${caseLabel}` : ` · #${caseId}`}
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
          <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
            <strong>督导越权移交</strong> — 跳过催收员申请-审批环节,直接把案件 stage
            置为「legal」。适用于:业主长期失联+大额欠费+无需催收员介入的案件。
            操作会写 audit log,留痕可追溯。
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              移交原因 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              placeholder="必填,说明为何直接移交(如:业主失联 60 天 + 欠费 ¥20000 + 资产线索充足,无需继续电话催收)"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
              autoFocus
            />
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
            className="px-4 py-1.5 text-sm rounded text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
            style={{ background: "#7e3af2" }}
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            确认移交
          </button>
        </div>
      </div>
    </div>
  );
}
