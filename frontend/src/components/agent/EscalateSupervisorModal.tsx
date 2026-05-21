// v0.5.4 — 催收员「升级督导」弹窗
// 后端:POST /api/v1/agent/cases/{caseId}/intent
//      body: { action: "transfer_supervisor", note?: string }
// 工作台 + 案件详情两个入口共用同一组件(SSOT)。
import { useCustomMutation } from "@refinedev/core";
import { Headphones, Loader2, X } from "lucide-react";
import { useState } from "react";

export function EscalateSupervisorModal({
  caseId,
  onClose,
  onSubmitted,
}: {
  caseId: number;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [note, setNote] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    mutate(
      {
        url: `agent/cases/${caseId}/intent`,
        method: "post",
        values: {
          action: "transfer_supervisor",
          note: note.trim() || undefined,
        },
      },
      {
        onSuccess: () => onSubmitted(),
        onError: (err) =>
          alert(
            `升级失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <div className="flex items-center gap-2">
            <Headphones className="w-5 h-5 text-amber-600" />
            <h2 className="text-base font-semibold">升级督导 — 案件 #{caseId}</h2>
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
          <div className="text-xs text-[var(--color-neutral-700)] bg-amber-50 border border-amber-200 rounded p-3 leading-relaxed">
            <div className="font-medium text-amber-800 mb-1">
              什么情况下升级督导?
            </div>
            <ul className="list-disc pl-4 space-y-0.5">
              <li>业主长期失联(&gt;1 个月),自己已多次尝试无果</li>
              <li>大额欠费但业主已多次承诺却反复违约</li>
              <li>业主投诉到物业 / 上访 / 媒体曝光风险</li>
              <li>沟通复杂(语言/家庭情况),个人推不动</li>
              <li>需要督导介入监听 / 接管下次通话</li>
            </ul>
            <div className="mt-2 text-amber-700 text-[11px]">
              升级后:督导接到通知,可介入处理或重新分配。
            </div>
          </div>

          <label className="block text-sm font-medium text-[var(--color-neutral-700)]">
            升级原因(选填)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            placeholder="选填:具体说明上面哪种情况,便于督导快速接手"
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
            disabled={mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            升级到督导
          </button>
        </div>
      </div>
    </div>
  );
}
