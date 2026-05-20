// v0.5.4 — 催收员「申请转法务」弹窗
// reason 必填(预设原因列表 + 「其他」时强制补充);提交后写 LegalConversionRequest
// 后端:POST /api/v1/agent/cases/{caseId}/intent
//       body: { action: "transfer_legal", note: string }
// 工作台 + 案件详情两个入口共用同一组件(SSOT)。
//
// v0.5.8 — 从中间 Modal 迁移到 RightDrawer 520px(决策矩阵:7 预设原因列表 + 提交前
// 需对照案件状态判断是否真该转法务);详见 docs/UI_PATTERNS_MODAL.md
import { useCustomMutation } from "@refinedev/core";
import { Loader2, Scale } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../ui/RightDrawer";

const PRESET_REASONS = [
  "业主长期失联(>1 个月)",
  "业主反复拒绝沟通",
  "大额欠费(>¥10000)且账龄长",
  "业主明确否认债务",
  "已多次承诺但反复违约",
  "走司法可能性高(业主有资产)",
  "其他",
] as const;

type PresetReason = (typeof PRESET_REASONS)[number];

export function RequestLegalConversionModal({
  caseId,
  caseLabel,
  onClose,
  onSubmitted,
}: {
  caseId: number;
  caseLabel?: string; // 案件简要(如「张三 · 5-203」)用于弹窗 header,可空
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [selected, setSelected] = useState<PresetReason | null>(null);
  const [supplement, setSupplement] = useState("");
  const { mutate, mutation } = useCustomMutation();

  const isOther = selected === "其他";
  const supplTrim = supplement.trim();
  // "其他"必填补充;非"其他"时补充选填
  const canSubmit = selected != null && (!isOther || supplTrim.length > 0);

  function buildNote(): string {
    if (!selected) return "";
    if (isOther) return supplTrim;
    return supplTrim ? `${selected}\n补充:${supplTrim}` : selected;
  }

  const handleSubmit = () => {
    if (!canSubmit) return;
    const note = buildNote();
    mutate(
      {
        url: `agent/cases/${caseId}/intent`,
        method: "post",
        values: { action: "transfer_legal", note },
      },
      {
        onSuccess: () => onSubmitted(),
        onError: (err) =>
          alert(
            `申请失败:${(err as { message?: string }).message ?? "请重试"}`,
          ),
      },
    );
  };

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="request-legal-conversion"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <Scale className="w-5 h-5" style={{ color: "#7e3af2" }} />
          申请转法务{caseLabel ? ` — ${caseLabel}` : ` — 案件 #${caseId}`}
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
            disabled={!canSubmit || mutation.isPending}
            className="px-4 py-1.5 text-sm rounded text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
            style={{ background: "#7e3af2" }}
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            提交申请
          </button>
        </>
      }
    >
      <div className="space-y-3">
          <div className="text-xs text-[var(--color-neutral-600)] bg-amber-50 border border-amber-200 rounded p-2">
            <strong>什么情况下转法务?</strong> 当本案件已无法通过电话/上门催回,
            且业主有偿还能力却拒绝履行时,可申请转法务。提交后督导/物业管理员审批,
            通过后由物业法务接单选服务包(律师函 / 调解 / 诉讼)。
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-2">
              转法务理由 <span className="text-red-500">*</span>
            </label>
            <div className="space-y-1.5">
              {PRESET_REASONS.map((r) => (
                <label
                  key={r}
                  className={`flex items-start gap-2 p-2 border rounded cursor-pointer transition ${
                    selected === r
                      ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]"
                      : "border-[var(--color-neutral-200)] hover:bg-[var(--color-neutral-50)]"
                  }`}
                >
                  <input
                    type="radio"
                    name="legal_reason"
                    checked={selected === r}
                    onChange={() => setSelected(r)}
                    className="mt-1"
                  />
                  <span className="text-sm">{r}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              {isOther ? (
                <>
                  补充说明 <span className="text-red-500">*</span>(选「其他」需说明具体情况)
                </>
              ) : (
                <>补充说明(选填)</>
              )}
            </label>
            <textarea
              value={supplement}
              onChange={(e) => setSupplement(e.target.value)}
              rows={3}
              placeholder={
                isOther
                  ? "必填:简述具体情况,便于审批人/法务理解"
                  : "选填:补充信息(如承诺日期 / 业主家庭背景 / 已尝试方式等)"
              }
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            />
          </div>
      </div>
    </RightDrawer>
  );
}
