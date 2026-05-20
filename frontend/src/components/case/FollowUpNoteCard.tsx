// v1.6.10 — 添加跟进备注卡（admin / agent / supervisor 案件详情共用）
// 调用方传入 endpoint（如 "agent/cases/{id}/stage" 或 "admin/cases/{id}/stage"）
// v0.5.6 — 阶段选「承诺缴费」时不再直接 PATCH,而是弹 MarkPromiseModal 让用户填
//          结构化字段(承诺什么/金额/日期),完整数据再 PATCH。
import { useCustomMutation, useInvalidate } from "@refinedev/core";
import { Save } from "lucide-react";
import { useState } from "react";
import { STAGE_LABELS } from "./constants";
import { MarkPromiseModal } from "./MarkPromiseModal";

interface Props {
  caseId: number;
  /** PATCH endpoint，例如 "agent/cases/123/stage" */
  endpoint: string;
  /** 成功后用于 invalidate 列表/详情缓存的 resource 名（例如 "agent/cases"） */
  invalidateResource?: string;
  onSaved?: () => void;
}

export function FollowUpNoteCard({
  caseId,
  endpoint,
  invalidateResource,
  onSaved,
}: Props) {
  const [note, setNote] = useState("");
  const [stage, setStage] = useState("");
  const [promiseModalOpen, setPromiseModalOpen] = useState(false);
  const { mutate, mutation } = useCustomMutation();
  const invalidate = useInvalidate();

  function invalidateAndReset() {
    setNote("");
    setStage("");
    if (invalidateResource) {
      void invalidate({
        resource: invalidateResource,
        invalidates: ["detail"],
        id: caseId,
      });
    }
    onSaved?.();
  }

  function handleSave() {
    if (!stage) return;
    // v0.5.6 — 承诺缴费走结构化弹窗,不走简单 PATCH
    if (stage === "promised") {
      setPromiseModalOpen(true);
      return;
    }
    mutate(
      {
        url: endpoint,
        method: "patch",
        values: { stage, note: note || undefined },
      },
      {
        onSuccess: () => invalidateAndReset(),
        onError: (err) => alert(`保存失败：${err.message ?? "请重试"}`),
      },
    );
  }

  return (
    <div className="ds-card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <span className="card-title">添加跟进备注</span>
      </div>
      <div
        className="card-body"
        style={{ display: "flex", flexDirection: "column", gap: 10 }}
      >
        <textarea
          className="form-control"
          placeholder="记录本次跟进情况、业主态度、下一步计划..."
          style={{ height: 80, resize: "vertical" }}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div>
          <label
            style={{
              display: "block",
              fontSize: 12,
              color: "#374151",
              fontWeight: 500,
              marginBottom: 4,
            }}
          >
            更新阶段
          </label>
          <select
            className="form-control"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          >
            <option value="">— 不变更 —</option>
            {Object.entries(STAGE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          style={{ width: "100%", justifyContent: "center" }}
          disabled={!stage || mutation.isPending}
          onClick={handleSave}
        >
          <Save className="w-3.5 h-3.5" />
          {mutation.isPending ? "保存中…" : "保存"}
        </button>
      </div>

      {promiseModalOpen && (
        <MarkPromiseModal
          caseId={caseId}
          endpoint={endpoint}
          open
          onClose={() => setPromiseModalOpen(false)}
          onSuccess={() => {
            setPromiseModalOpen(false);
            invalidateAndReset();
          }}
        />
      )}
    </div>
  );
}
