// v0.6.0 — 案件详情页内直接审批转法务申请(不再跳列表 inbox)。
//
// 用法:仅当 case.pending_legal_conversion_request_id != null 时打开。
// 内部:GET /api/v1/legal-conversion-requests/{id} → 显示申请详情;
//      底部 [驳回] [批准] 直接调对应后端端点。
import { useCustom, useCustomMutation } from "@refinedev/core";
import { CheckCircle2, Loader2, Scale, X } from "lucide-react";
import { useState } from "react";

interface RequestDetail {
  id: number;
  case_id: number;
  requester_name: string | null;
  requester_role: string;
  reason: string | null;
  status: string;
  created_at: string;
}

interface Props {
  requestId: number;
  caseLabel?: string;
  onClose: () => void;
  onDone: () => void;  // approve/reject 任一完成后触发(调用方负责 refetch)
}

export function LegalConversionApprovalModal({
  requestId, caseLabel, onClose, onDone,
}: Props) {
  const [rejectReason, setRejectReason] = useState("");
  const [rejectMode, setRejectMode] = useState(false);

  const { query } = useCustom<RequestDetail>({
    url: `legal-conversion-requests/${requestId}`,
    method: "get",
    queryOptions: { enabled: requestId > 0 },
  });
  const detail = query.data?.data;

  const { mutate: approve, mutation: approveMutation } = useCustomMutation();
  const { mutate: reject, mutation: rejectMutation } = useCustomMutation();
  const pending = approveMutation.isPending || rejectMutation.isPending;

  const handleApprove = () => {
    approve(
      {
        url: `legal-conversion-requests/${requestId}/approve`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => alert(`批准失败:${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const handleReject = () => {
    const trimmed = rejectReason.trim();
    if (!trimmed) return;
    reject(
      {
        url: `legal-conversion-requests/${requestId}/reject`,
        method: "post",
        values: { reason: trimmed },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => alert(`驳回失败:${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)]">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Scale className="w-5 h-5 text-violet-600" />
            审批转法务申请 #{requestId}
            {caseLabel && <span className="text-sm text-[var(--color-neutral-500)]">· {caseLabel}</span>}
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
          {query.isLoading ? (
            <div className="py-8 text-center text-sm text-[var(--color-neutral-500)]">
              加载中…
            </div>
          ) : !detail ? (
            <div className="py-8 text-center text-sm text-red-600">
              申请不存在或无权访问
            </div>
          ) : (
            <>
              <div className="text-xs bg-[var(--color-neutral-50)] rounded p-3 space-y-1">
                <div>
                  <span className="text-[var(--color-neutral-500)]">申请人:</span>
                  {" "}{detail.requester_name ?? "—"}({detail.requester_role})
                </div>
                <div>
                  <span className="text-[var(--color-neutral-500)]">提交时间:</span>
                  {" "}{new Date(detail.created_at).toLocaleString("zh-CN")}
                </div>
                <div>
                  <span className="text-[var(--color-neutral-500)]">当前状态:</span>
                  {" "}{detail.status}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                  申请理由
                </label>
                <div className="text-sm p-2 bg-amber-50 border border-amber-200 rounded whitespace-pre-wrap">
                  {detail.reason ?? "—"}
                </div>
              </div>

              {rejectMode && (
                <div>
                  <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                    驳回理由 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    rows={3}
                    placeholder="必填,向催收员说明为何不批准(如:催收次数不够 / 业主已有承诺方案)"
                    className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
                    autoFocus
                  />
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-[var(--color-neutral-200)]">
          {rejectMode ? (
            <>
              <button
                type="button"
                onClick={() => { setRejectMode(false); setRejectReason(""); }}
                className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
              >
                返回
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={!rejectReason.trim() || pending}
                className="px-4 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {pending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                提交驳回
              </button>
            </>
          ) : (
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
                onClick={() => setRejectMode(true)}
                disabled={pending || !detail}
                className="px-4 py-1.5 text-sm rounded border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                驳回申请
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={pending || !detail}
                className="px-4 py-1.5 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {pending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <CheckCircle2 className="w-3.5 h-3.5" />
                批准转法务
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
