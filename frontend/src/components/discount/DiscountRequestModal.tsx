// v1.6.9 — 发起减免申请 Modal（催收员 / 督导 共用）
// 提交后端 POST /cases/{case_id}/discount-offers，后端按租户阈值自动判定走督导还是 admin 审批
import { Loader2, BadgePercent, X } from "lucide-react";
import { useMemo, useState } from "react";
import { OFFER_TYPE_LABELS, type OfferType } from "../../pages/discount/_mock";
import { useCreateDiscountOffer } from "../../pages/discount/api";

interface Props {
  caseId: number;
  /** 案件原欠费金额（用作 original_amount 默认值，催收员一般不改）*/
  originalAmount: number | null;
  ownerName?: string | null;
  onClose: () => void;
  onSuccess: (offerId: number) => void;
}

export function DiscountRequestModal({
  caseId,
  originalAmount,
  ownerName,
  onClose,
  onSuccess,
}: Props) {
  const [offerType, setOfferType] = useState<OfferType>("principal_discount");
  const [original, setOriginal] = useState<string>(
    originalAmount != null ? String(originalAmount) : "",
  );
  const [proposed, setProposed] = useState<string>("");
  const [installmentMonths, setInstallmentMonths] = useState<string>("3");
  const [reason, setReason] = useState("");
  const { createOffer, isPending } = useCreateDiscountOffer();

  const originalNum = Number(original);
  const proposedNum = Number(proposed);
  const discountPct = useMemo(() => {
    if (!originalNum || originalNum <= 0) return 0;
    if (offerType === "installment") return 0;  // 分期不打折
    const cut = originalNum - proposedNum;
    return Math.round((cut / originalNum) * 1000) / 10;  // 一位小数
  }, [originalNum, proposedNum, offerType]);

  const isInstallment = offerType === "installment";

  const canSubmit =
    !isPending &&
    originalNum > 0 &&
    proposedNum > 0 &&
    proposedNum <= originalNum &&
    reason.trim().length >= 4 &&
    (!isInstallment || Number(installmentMonths) >= 1);

  function handleSubmit() {
    if (!canSubmit) return;
    createOffer(
      {
        case_id: caseId,
        offer_type: offerType,
        original_amount: originalNum,
        proposed_amount: proposedNum,
        installment_months: isInstallment ? Number(installmentMonths) : null,
        reason: reason.trim(),
      },
      {
        onSuccess: (o) => onSuccess(o.id),
        onError: (e) => {
          const msg = (e as { message?: string }).message ?? "请重试";
          alert(`减免申请失败：${msg}`);
        },
      },
    );
  }

  // 大致预测审批走向（仅用于 UX 提示，最终以后端为准）
  let approvalHint = "";
  if (discountPct >= 30) approvalHint = "比例较大，将转物业管理员审批";
  else if (discountPct >= 10) approvalHint = "需督导审批";
  else if (discountPct > 0) approvalHint = "比例较小，可能自动通过";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-lg max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-neutral-200)] sticky top-0 bg-white">
          <div className="flex items-center gap-2">
            <BadgePercent className="w-5 h-5 text-[var(--color-warning)]" />
            <h2 className="text-base font-semibold">
              发起减免申请{ownerName ? ` — ${ownerName}` : ""}
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
          {/* 减免类型 */}
          <section>
            <label className="block text-sm font-semibold mb-2">减免类型</label>
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(OFFER_TYPE_LABELS) as OfferType[]).map((t) => (
                <label
                  key={t}
                  className={`flex items-center gap-2 p-2.5 border rounded cursor-pointer text-sm ${
                    offerType === t
                      ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]"
                      : "border-[var(--color-neutral-200)] hover:bg-[var(--color-neutral-50)]"
                  }`}
                >
                  <input
                    type="radio"
                    name="offer_type"
                    checked={offerType === t}
                    onChange={() => setOfferType(t)}
                  />
                  {OFFER_TYPE_LABELS[t]}
                </label>
              ))}
            </div>
          </section>

          {/* 金额 */}
          <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label className="block text-sm font-semibold mb-1">原欠费金额（¥）</label>
              <input
                type="number"
                min={0}
                step={0.01}
                value={original}
                onChange={(e) => setOriginal(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-1">
                {isInstallment ? "首期金额（¥）" : "业主同意支付（¥）"}
              </label>
              <input
                type="number"
                min={0}
                step={0.01}
                value={proposed}
                onChange={(e) => setProposed(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
              />
            </div>
          </section>

          {/* 分期月数 */}
          {isInstallment && (
            <section>
              <label className="block text-sm font-semibold mb-1">分期月数</label>
              <input
                type="number"
                min={1}
                max={36}
                step={1}
                value={installmentMonths}
                onChange={(e) => setInstallmentMonths(e.target.value)}
                className="w-32 px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
              />
            </section>
          )}

          {/* 折扣计算 */}
          {!isInstallment && originalNum > 0 && proposedNum > 0 && (
            <div
              className="text-xs"
              style={{
                padding: 8,
                background: discountPct >= 30 ? "#fef2f2" : discountPct >= 10 ? "#fffbeb" : "#f0fdf4",
                border: "1px solid",
                borderColor: discountPct >= 30 ? "#fecaca" : discountPct >= 10 ? "#fde68a" : "#bbf7d0",
                borderRadius: 4,
                color: discountPct >= 30 ? "#991b1b" : discountPct >= 10 ? "#92400e" : "#14532d",
              }}
            >
              减免比例 <strong>{discountPct}%</strong>
              {approvalHint && <span> · {approvalHint}</span>}
            </div>
          )}

          {/* 理由 */}
          <section>
            <label className="block text-sm font-semibold mb-1">
              申请理由 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="必填，简述业主原话 + 你的判断（如：业主家庭经济困难，可一次性结清 6000）"
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
            disabled={!canSubmit}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            提交申请
          </button>
        </div>
      </div>
    </div>
  );
}
