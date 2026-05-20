// v0.5.6 — 标记承诺缴费独立弹窗(替代之前的 window.prompt + 简单备注)。
//
// 诱因:旧实现「标记承诺缴费」只把 stage 改成 'promised' + 写一条自由文本备注,业主
// 到底承诺什么、承诺多少、什么时候缴全部丢在 note 里,报表/提醒/兑现追踪拿不到结构化数据。
// 本组件在前端把这 3 件事拆成结构化字段,后端写到 CollectionCase.promise_content /
// promise_amount / promise_due_at,详见 PRD §13.5 + alembic 24025_v056_promise_fields。
//
// v0.5.8 — 从中间 Modal 迁移到 RightDrawer 520px(决策矩阵:表单 ≥ 4 字段 + 需边看
// 案件金额/时间线对得上承诺金额);详见 docs/UI_PATTERNS_MODAL.md
//
// 同一组件同时给催收员工作台 + 案件详情 + 督导 + 物业管理员四端复用。
import { useCustomMutation } from "@refinedev/core";
import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../ui/RightDrawer";

const PRESET_CONTENTS = [
  "全额缴清",
  "先缴本金,违约金后续协商",
  "先缴一半,剩余分期",
  "分期 2 次(本月 50% + 下月 50%)",
  "分期 3 次(每月 1/3)",
  "其他(下方补充说明)",
] as const;

export interface MarkPromiseModalProps {
  /** 案件 ID */
  caseId: number;
  /** PATCH 端点(如 "agent/cases/{id}/stage" 或 "admin/cases/{id}/stage")— 调用方拼好 */
  endpoint: string;
  open: boolean;
  onClose: () => void;
  /** 提交成功后调用,用于刷新列表 / 关闭弹窗 / toast 等 */
  onSuccess?: () => void;
}

export function MarkPromiseModal({
  caseId,
  endpoint,
  open,
  onClose,
  onSuccess,
}: MarkPromiseModalProps) {
  const [presetIdx, setPresetIdx] = useState<number>(0);
  const [customContent, setCustomContent] = useState("");
  const [amount, setAmount] = useState("");
  const [dueDate, setDueDate] = useState(""); // YYYY-MM-DD
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { mutate } = useCustomMutation();

  if (!open) return null;

  const presetText = PRESET_CONTENTS[presetIdx] ?? "";
  const isOther = presetIdx === PRESET_CONTENTS.length - 1;
  // 组合最终 promise_content:预设 + 自由补充(如果有)
  const finalContent = isOther
    ? customContent.trim()
    : customContent.trim()
      ? `${presetText} — ${customContent.trim()}`
      : presetText;

  const canSubmit = !!finalContent && !!dueDate && !submitting;

  const handleSubmit = () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);

    const payload: Record<string, unknown> = {
      stage: "promised",
      promise_content: finalContent,
      // 后端接受 ISO datetime;补全 00:00:00Z
      promise_due_at: new Date(`${dueDate}T00:00:00Z`).toISOString(),
    };
    if (amount.trim()) {
      payload.promise_amount = amount.trim();
    }
    if (note.trim()) {
      payload.note = note.trim();
    }

    mutate(
      {
        url: endpoint,
        method: "patch",
        values: payload,
      },
      {
        onSuccess: () => {
          setSubmitting(false);
          // 重置表单,避免再次打开时旧数据残留
          setPresetIdx(0);
          setCustomContent("");
          setAmount("");
          setDueDate("");
          setNote("");
          onSuccess?.();
          onClose();
        },
        onError: (err: { message?: string }) => {
          setSubmitting(false);
          setError(err?.message ?? "标记失败,请稍后重试");
        },
      },
    );
  };

  // 默认承诺日期建议:今天 + 14 天
  const minDate = new Date().toISOString().slice(0, 10);

  return (
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="mark-promise"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-600" />
          标记承诺缴费 — 案件 #{caseId}
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
            disabled={!canSubmit}
            className="px-4 py-1.5 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            {submitting ? "提交中…" : "标记承诺缴费"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
          <div className="text-xs text-[var(--color-neutral-600)] bg-blue-50 border border-blue-200 rounded p-2">
            <strong>提示</strong>:把业主的承诺写成结构化字段(承诺什么/金额/日期),系统
            会在到期前 24 小时自动提醒你回访,兑现追踪也能上报。
          </div>

          {/* 承诺内容 */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
              承诺内容 <span className="text-red-500">*</span>
            </label>
            <select
              value={presetIdx}
              onChange={(e) => setPresetIdx(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
            >
              {PRESET_CONTENTS.map((label, i) => (
                <option key={label} value={i}>{label}</option>
              ))}
            </select>
            <input
              type="text"
              value={customContent}
              onChange={(e) => setCustomContent(e.target.value)}
              placeholder={
                isOther ? "请说明承诺内容" : "(可选)补充说明,如「先缴 3000 元」"
              }
              maxLength={400}
              className="mt-1.5 w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
            />
          </div>

          {/* 承诺缴费日期 + 金额 同一行 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
                承诺缴费日期 <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={dueDate}
                min={minDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
                承诺金额(元)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="(可空)如 5000"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded"
              />
            </div>
          </div>

          {/* 备注 */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1.5">
              备注
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="(可选)业主当时的态度 / 上下文,如「业主说月底发工资,可全额缴」"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-300)] rounded resize-none"
            />
          </div>

          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {error}
            </div>
          )}
      </div>
    </RightDrawer>
  );
}
