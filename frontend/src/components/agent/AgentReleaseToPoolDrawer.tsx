// v0.9.0 — 催收员把案件放回公海(必填理由)
//
// 替换原 window.confirm 直接确认。理由必填,写入 audit_log payload 用于复盘
// (5 次拨打未接 / 业主拒缴 / 产权转移 等场景)。
//
// 后端:POST /api/v1/agent/cases/{case_id}/release { reason: str (1-500) }
import { useCustomMutation } from "@refinedev/core";
import { Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../ui/RightDrawer";

interface Props {
  caseId: number;
  ownerName?: string;
  onClose: () => void;
  onDone: () => void;
}

const REASON_HINTS = [
  "5 次拨打未接",
  "业主明确拒缴",
  "产权转移,联系不到新业主",
  "业主联系方式已失效",
  "项目已结案",
];

export function AgentReleaseToPoolDrawer({
  caseId,
  ownerName,
  onClose,
  onDone,
}: Props) {
  const [reason, setReason] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const validReason = reason.trim().length > 0 && reason.length <= 500;

  const handleSubmit = () => {
    if (!validReason) return;
    mutate(
      {
        url: `agent/cases/${caseId}/release`,
        method: "post",
        values: { reason: reason.trim() },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) =>
          alert(
            `释放失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="agent-release-to-pool"
      defaultWidth={480}
      title={
        <span className="flex items-center gap-2">
          <RotateCcw className="w-5 h-5 text-[var(--color-warning)]" />
          放回公海{ownerName ? ` — ${ownerName}` : ""}
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
            disabled={!validReason || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-warning)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            确认放回
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-warning)] bg-[var(--color-warning-soft,#FFFBEB)] rounded p-2.5 border border-[#FDE68A]">
          <strong>⚠️ 注意</strong>:放回后该案件不再属于你,其他催收员可领。
          理由会进入审计日志,督导和管理员可看到。
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
            放回理由 <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
            rows={4}
            placeholder="如:多次拨打未接 / 业主明确拒缴 / 产权转移..."
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            autoFocus
          />
          <div className="flex items-center justify-between mt-1">
            <span className="text-xs text-[var(--color-neutral-400)]">
              {reason.length} / 500
            </span>
            {!validReason && reason.length === 0 && (
              <span className="text-xs text-[var(--color-neutral-400)]">
                必填
              </span>
            )}
          </div>
        </div>

        <div>
          <div className="text-xs text-[var(--color-neutral-500)] mb-1.5">
            常用理由(点击填入):
          </div>
          <div className="flex flex-wrap gap-1.5">
            {REASON_HINTS.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setReason(h)}
                className="text-xs px-2 py-1 rounded border border-[var(--color-neutral-200)] bg-[var(--color-neutral-50)] hover:bg-[var(--color-neutral-100)] text-[var(--color-neutral-700)]"
              >
                {h}
              </button>
            ))}
          </div>
        </div>
      </div>
    </RightDrawer>
  );
}
