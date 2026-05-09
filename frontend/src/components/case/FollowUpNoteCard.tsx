// v1.6.10 — 添加跟进备注卡（admin / agent / supervisor 案件详情共用）
// 调用方传入 endpoint（如 "agent/cases/{id}/stage" 或 "admin/cases/{id}/stage"）
import { useCustomMutation, useInvalidate } from "@refinedev/core";
import { Save } from "lucide-react";
import { useState } from "react";
import { STAGE_LABELS } from "./constants";

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
  const { mutate, mutation } = useCustomMutation();
  const invalidate = useInvalidate();

  function handleSave() {
    if (!stage) return;
    mutate(
      {
        url: endpoint,
        method: "patch",
        values: { stage, note: note || undefined },
      },
      {
        onSuccess: () => {
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
        },
        onError: (err) => alert(`保存失败：${err.message ?? "请重试"}`),
      },
    );
  }

  return (
    <div className="ds-card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <span className="card-title">添加跟进备注</span>
      </div>
      <div className="card-body">
        <textarea
          className="form-control"
          placeholder="记录本次跟进情况、业主态度、下一步计划..."
          style={{ height: 80 }}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#374151", fontWeight: 500 }}>
              更新阶段：
            </span>
            <select
              className="form-control"
              style={{ width: 140 }}
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
            disabled={!stage || mutation.isPending}
            onClick={handleSave}
          >
            <Save className="w-3.5 h-3.5" />
            {mutation.isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
