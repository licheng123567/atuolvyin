// Sprint 16.1 — 法务转化下单弹窗（PRD §20.4）
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

interface PreviewResp {
  timeline_summary: {
    total_calls: number;
    total_minutes: number;
    first_contact_at: string | null;
    last_contact_at: string | null;
    result_tag_breakdown: Record<string, number>;
    stage: string;
    amount_owed: number | null;
    months_overdue: number | null;
  };
  recommendation: {
    slug: string;
    reason: string;
    confidence: number;
    notes: string[];
  };
  available_packages: PackageItem[];
}

interface ApproveContext {
  // v1.6.8 — approve mode：申请人 / 申请理由透传，方便审批人参考
  requesterName?: string | null;
  reason?: string | null;
}

export function ConvertToLegalModal({
  caseId,
  onClose,
  onSuccess,
  mode = "create",
  requestId,
  approveContext,
}: {
  caseId: number;
  onClose: () => void;
  onSuccess: (orderId: number) => void;
  // v1.6.8 — mode='approve' 时调审批端点（POST legal-conversion-requests/{id}/approve），
  //          创建 Order 同时把 request 标 approved。
  mode?: "create" | "approve";
  requestId?: number;
  approveContext?: ApproveContext;
}) {
  const [selectedPkgId, setSelectedPkgId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  const { query } = useCustom<PreviewResp>({
    url: `admin/cases/${caseId}/legal-conversion-preview`,
    method: "get",
  });
  const preview = query.data?.data;

  const { mutate, mutation } = useCustomMutation();

  const recommendedPkgId = preview?.available_packages.find(
    (p) => p.slug === preview.recommendation.slug,
  )?.id;
  const effectiveSel = selectedPkgId ?? recommendedPkgId ?? null;

  const isApprove = mode === "approve" && requestId != null;
  // v0.5.4 — approve 模式不再要求选服务包(改由法务在 /legal-finalize 选);
  // create 模式仍需选包(物业 admin 直接建单)
  const canSubmit = isApprove ? true : effectiveSel != null;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const url = isApprove
      ? `legal-conversion-requests/${requestId}/approve`
      : `admin/cases/${caseId}/convert-to-legal`;
    // approve body 不含 package_id(后端会忽略;新流程服务包由法务在 /legal-finalize 选)
    const values = isApprove
      ? { notes: notes.trim() || undefined }
      : { package_id: effectiveSel, notes: notes.trim() || undefined };
    mutate(
      {
        url,
        method: "post",
        values,
      },
      {
        onSuccess: (data) => {
          if (isApprove) {
            // approve 端点返回 LegalConversionRequestOut(状态变为 approved_pending_legal,
            // related_order_id 此时仍为 null,等法务接单时才创建 Order)
            const req = data?.data as { related_order_id?: number };
            onSuccess(req.related_order_id ?? 0);
          } else {
            const order = data?.data as { id: number };
            onSuccess(order.id);
          }
        },
        onError: (err) => {
          const verb = isApprove ? "审批" : "下单";
          alert(`${verb}失败:${(err as { message?: string }).message ?? "请重试"}`);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)] sticky top-0 bg-white">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-base font-semibold">
              {mode === "approve"
                ? `批准转法务申请${requestId ? ` #${requestId}` : ""}`
                : "转法务追诉"}
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
          {query.isLoading && (
            <div className="flex items-center gap-2 text-sm text-[var(--color-neutral-500)]">
              <Loader2 className="w-4 h-4 animate-spin" />
              生成催收时间线 + 推荐方案中…
            </div>
          )}

          {mode === "approve" && approveContext && (
            <section className="bg-blue-50 border border-blue-200 rounded p-3 text-xs space-y-1">
              <div>
                <span className="text-blue-700 font-medium">申请人：</span>
                <span className="text-blue-900">{approveContext.requesterName ?? "—"}</span>
              </div>
              <div>
                <span className="text-blue-700 font-medium">申请理由：</span>
                <span className="text-blue-900 whitespace-pre-wrap">
                  {approveContext.reason ?? "（未填写）"}
                </span>
              </div>
            </section>
          )}

          {preview && (
            <>
              <section>
                <h3 className="text-sm font-semibold mb-2">催收时间线摘要</h3>
                <div className="bg-[var(--color-neutral-50)] rounded p-3 text-xs text-[var(--color-neutral-700)] space-y-1">
                  <div>共 {preview.timeline_summary.total_calls} 通通话 · {preview.timeline_summary.total_minutes} 分钟</div>
                  {preview.timeline_summary.first_contact_at && (
                    <div>
                      首次接触：{new Date(preview.timeline_summary.first_contact_at).toLocaleString("zh-CN")}
                    </div>
                  )}
                  {preview.timeline_summary.last_contact_at && (
                    <div>
                      最近接触：{new Date(preview.timeline_summary.last_contact_at).toLocaleString("zh-CN")}
                    </div>
                  )}
                  {Object.keys(preview.timeline_summary.result_tag_breakdown).length > 0 && (
                    <div>
                      结果分布：
                      {Object.entries(preview.timeline_summary.result_tag_breakdown)
                        .map(([tag, n]) => `${tag} ${n}`)
                        .join(" · ")}
                    </div>
                  )}
                  {preview.timeline_summary.amount_owed != null && (
                    <div>
                      欠费金额 ¥{preview.timeline_summary.amount_owed.toLocaleString()}
                      {preview.timeline_summary.months_overdue != null &&
                        ` · 逾期 ${preview.timeline_summary.months_overdue} 个月`}
                    </div>
                  )}
                </div>
              </section>

              {/* v0.5.4 — 系统推荐 + 选择服务包仅 create 模式显示;approve 模式由法务在 /legal-finalize 阶段选 */}
              {!isApprove && (
              <>
              <section>
                <h3 className="text-sm font-semibold mb-2">系统推荐</h3>
                <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs">
                  <div className="font-medium text-amber-800">
                    推荐：{preview.available_packages.find((p) => p.slug === preview.recommendation.slug)?.name ?? preview.recommendation.slug}
                  </div>
                  <div className="text-amber-700 mt-0.5">
                    {preview.recommendation.reason}（置信度 {(preview.recommendation.confidence * 100).toFixed(0)}%）
                  </div>
                  {preview.recommendation.notes.length > 0 && (
                    <ul className="list-disc pl-5 mt-1 text-amber-600">
                      {preview.recommendation.notes.map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              <section>
                <h3 className="text-sm font-semibold mb-2">选择服务包</h3>
                <div className="space-y-2">
                  {preview.available_packages.map((p) => {
                    const checked = effectiveSel === p.id;
                    const isRec = p.id === recommendedPkgId;
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
                            {isRec && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                                推荐
                              </span>
                            )}
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
              </>
              )}

              {isApprove && (
                <section className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-800">
                  ⚠ 审批仅表示同意转出案件给法务。批准后申请进入「待法务接单」队列,由法务接单时选定服务包并创建订单。
                </section>
              )}

              <section>
                <label className="block text-sm font-semibold mb-1">备注</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="选填，如已联络情况、特殊说明等"
                  className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
                />
              </section>
            </>
          )}
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
            disabled={!canSubmit || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {isApprove ? "批准转出" : "提交订单"}
          </button>
        </div>
      </div>
    </div>
  );
}
