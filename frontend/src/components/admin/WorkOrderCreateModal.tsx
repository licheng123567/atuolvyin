// v2.2 — 统一的「创建工单」弹窗（取代 case 详情页的 window.prompt 流）
// 与其他 inline-modal 创建流一致：ds-modal + 表单字段 + 错误内联展示。
import { useCustomMutation } from "@refinedev/core";
import { useState } from "react";
import {
  WORK_ORDER_PRIORITIES,
  WORK_ORDER_TYPES,
  formatPriority,
  formatType,
  type WorkOrderPriority,
  type WorkOrderType,
} from "../../pages/workorder/orders/helpers";

interface Props {
  caseId: number;
  onClose: () => void;
  onSuccess: (orderId?: number) => void;
}

export function WorkOrderCreateModal({ caseId, onClose, onSuccess }: Props) {
  // 默认类型用合法枚举值 "other"（旧代码误用 "case_followup" 触发后端 422）
  const [orderType, setOrderType] = useState<WorkOrderType>("other");
  const [priority, setPriority] = useState<WorkOrderPriority>("normal");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { mutate, mutation } = useCustomMutation();

  function submit() {
    setError(null);
    if (!description.trim()) {
      setError("请填写工单内容");
      return;
    }
    mutate(
      {
        url: "workorders",
        method: "post",
        values: {
          case_id: caseId,
          order_type: orderType,
          priority,
          description: description.trim(),
        },
      },
      {
        onSuccess: (resp) => {
          const wo = resp.data as { id?: number };
          onSuccess(wo.id);
        },
        onError: (err) => {
          const detail = (
            err as {
              response?: { data?: { detail?: { message?: string } | string } };
            }
          )?.response?.data?.detail;
          const msg =
            typeof detail === "string"
              ? detail
              : (detail?.message ?? err?.message ?? "创建失败");
          setError(msg);
        },
      },
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">创建工单</span>
          <button type="button" className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div
          className="modal-body"
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">
                工单类型<span className="req">*</span>
              </label>
              <select
                className="form-control"
                value={orderType}
                onChange={(e) => setOrderType(e.target.value as WorkOrderType)}
              >
                {WORK_ORDER_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {formatType(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">优先级</label>
              <select
                className="form-control"
                value={priority}
                onChange={(e) => setPriority(e.target.value as WorkOrderPriority)}
              >
                {WORK_ORDER_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {formatPriority(p)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">
              工单内容<span className="req">*</span>
            </label>
            <textarea
              className="form-control"
              style={{ minHeight: 100 }}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="详细描述需要协调员跟进的问题"
            />
          </div>
          {error && (
            <div
              style={{
                background: "var(--color-danger-light)",
                color: "var(--color-danger)",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="ds-btn ds-btn-secondary" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={submit}
            disabled={!description.trim() || mutation.isPending}
          >
            {mutation.isPending ? "创建中…" : "创建工单"}
          </button>
        </div>
      </div>
    </div>
  );
}
