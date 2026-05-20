// v0.5.4 — 物业法务「接单选服务包」弹窗
// 后端:POST /api/v1/legal-conversion-requests/{id}/legal-finalize
// body: { package_id: int, notes?: str }
// 状态流转:approved_pending_legal → approved + 建 LegalConversionOrder(internal_processing)
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Loader2, Scale, X } from "lucide-react";
import { useState } from "react";

interface PackageItem {
  id: number;
  slug: string;
  name: string;
  package_type: string;
  description: string | null;
  price: string;
}

export interface LegalFinalizeContext {
  requestId: number;
  caseId: number;
  ownerName: string | null;
  ownerRoom: string | null;
  projectName: string | null;
  amountOwed: string | null;
  requesterName: string | null;
  reason: string | null;
  reviewerNote: string | null;
  reviewerName: string | null;
}

export function LegalFinalizeModal({
  ctx,
  onClose,
  onFinalized,
}: {
  ctx: LegalFinalizeContext;
  onClose: () => void;
  onFinalized: (orderId: number) => void;
}) {
  const [selectedPkgId, setSelectedPkgId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  // legal 角色现在可读 /admin/legal-packages(Wave 4 后端守卫扩展)
  const { query } = useCustom<PackageItem[]>({
    url: "admin/legal-packages",
    method: "get",
  });
  const packages = query.data?.data ?? [];

  const { mutate, mutation } = useCustomMutation();

  const handleSubmit = () => {
    if (!selectedPkgId) return;
    mutate(
      {
        url: `legal-conversion-requests/${ctx.requestId}/legal-finalize`,
        method: "post",
        values: { package_id: selectedPkgId, notes: notes.trim() || undefined },
      },
      {
        onSuccess: (resp) => {
          const req = resp?.data as { related_order_id?: number };
          onFinalized(req.related_order_id ?? 0);
        },
        onError: (err) =>
          alert(
            `接单失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  const room = ctx.ownerRoom ?? "—";
  const amount = ctx.amountOwed
    ? `¥${Number(ctx.amountOwed).toLocaleString("zh-CN")}`
    : "—";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)] sticky top-0 bg-white">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-base font-semibold">
              法务接单选服务包 — 申请 #{ctx.requestId}
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

        <div className="p-5 space-y-4">
          {/* 案件 + 业主上下文 */}
          <section className="bg-[var(--color-neutral-50)] rounded p-3 text-xs space-y-1">
            <div>
              <span className="text-[var(--color-neutral-500)]">业主:</span>{" "}
              <strong>{ctx.ownerName ?? "—"}</strong>{" · "}
              <span className="text-[var(--color-neutral-500)]">房号:</span>{" "}
              {room}
              {ctx.projectName && (
                <>
                  {" · "}
                  <span className="text-[var(--color-neutral-500)]">项目:</span>{" "}
                  {ctx.projectName}
                </>
              )}
            </div>
            <div>
              <span className="text-[var(--color-neutral-500)]">欠费金额:</span>{" "}
              <span className="text-red-600 font-medium">{amount}</span>
              {" · "}
              <span className="text-[var(--color-neutral-500)]">案件 #</span>
              {ctx.caseId}
            </div>
          </section>

          {/* 催收员理由 + 督导/admin 备注 */}
          <section className="border border-blue-200 bg-blue-50 rounded p-3 text-xs space-y-1.5">
            <div>
              <span className="text-blue-700 font-medium">申请人:</span>{" "}
              <span className="text-blue-900">{ctx.requesterName ?? "—"}</span>
            </div>
            <div>
              <span className="text-blue-700 font-medium">催收员理由:</span>{" "}
              <span className="text-blue-900 whitespace-pre-wrap">
                {ctx.reason ?? "（未填写）"}
              </span>
            </div>
            {ctx.reviewerName && (
              <div>
                <span className="text-blue-700 font-medium">
                  审批人({ctx.reviewerName}):
                </span>{" "}
                <span className="text-blue-900 whitespace-pre-wrap">
                  {ctx.reviewerNote ?? "（无备注）"}
                </span>
              </div>
            )}
          </section>

          {/* 服务包选择(法务专享:显示价格 + 描述) */}
          <section>
            <h3 className="text-sm font-semibold mb-2">选择服务包</h3>
            {query.isLoading && (
              <div className="text-xs text-[var(--color-neutral-500)] flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> 加载服务包目录…
              </div>
            )}
            {packages.length === 0 && !query.isLoading && (
              <div className="text-xs text-[var(--color-neutral-500)]">
                暂无可用服务包(请联系平台 ops 配置)
              </div>
            )}
            <div className="space-y-2">
              {packages.map((p) => {
                const checked = selectedPkgId === p.id;
                return (
                  <label
                    key={p.id}
                    className={`flex items-start gap-2 p-3 border rounded cursor-pointer transition ${
                      checked
                        ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]"
                        : "border-[var(--color-neutral-200)] hover:bg-[var(--color-neutral-50)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="package"
                      checked={checked}
                      onChange={() => setSelectedPkgId(p.id)}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{p.name}</span>
                        <span className="text-sm font-mono text-[var(--color-primary)] ml-auto">
                          {parseFloat(p.price) > 0 ? `¥${p.price}` : "面议"}
                        </span>
                      </div>
                      {p.description && (
                        <div className="text-xs text-[var(--color-neutral-600)] mt-0.5">
                          {p.description}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </section>

          {/* 法务备注 */}
          <section>
            <label className="block text-sm font-semibold mb-1">
              法务备注(选填)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="如选包理由 / 对律所撮合的建议 / 特殊说明等"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            />
          </section>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-[var(--color-neutral-200)] sticky bottom-0 bg-white">
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
            disabled={!selectedPkgId || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            接单并下单
          </button>
        </div>
      </div>
    </div>
  );
}
