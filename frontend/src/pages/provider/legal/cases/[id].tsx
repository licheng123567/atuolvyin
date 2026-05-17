// §9 — 服务商法务·案件详情页 + 发起法务转化请求
import { ArrowLeft, X } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useGo } from "@refinedev/core";
import { useProviderLegalCase, useCreateConversionRequest } from "../api";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{value}</div>
    </div>
  );
}

export function ProviderLegalCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const caseId = Number(id);
  const go = useGo();
  const { detail, isLoading, isError } = useProviderLegalCase(caseId);
  const { create, isPending } = useCreateConversionRequest();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");

  if (isLoading) {
    return (
      <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载中…</div>
    );
  }

  if (isError || !detail) {
    return (
      <div style={{ padding: 24 }}>
        <button
          type="button"
          className="ds-btn ds-btn-ghost"
          style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 12 }}
          onClick={() => go({ to: "/provider/legal/cases" })}
        >
          <ArrowLeft size={14} /> 返回法务案件
        </button>
        <div className="ds-card">
          <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
            案件不存在或无权限
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = () => {
    const trimmed = reason.trim();
    if (!trimmed) {
      setErr("请填写申请理由");
      return;
    }
    setErr("");
    create(caseId, trimmed, {
      onSuccess: (r) => {
        go({ to: `/provider/legal/requests/${r.id}` });
      },
      onError: (e) => {
        const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
        setErr(msg ?? "提交失败");
      },
    });
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setReason("");
    setErr("");
  };

  return (
    <div style={{ padding: 24, maxWidth: 860 }}>
      {/* 返回链接 */}
      <button
        type="button"
        className="ds-btn ds-btn-ghost"
        style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 12 }}
        onClick={() => go({ to: "/provider/legal/cases" })}
      >
        <ArrowLeft size={14} /> 返回法务案件
      </button>

      {/* 顶部标题行 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>
          案件详情 · {detail.building}{detail.room} {detail.owner_name}
        </h1>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          onClick={() => setDialogOpen(true)}
        >
          发起法务转化请求
        </button>
      </div>

      {/* 案件信息卡 */}
      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>案件信息</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px 24px" }}>
            <Field label="业主" value={detail.owner_name ?? "—"} />
            <Field label="手机号" value={detail.owner_phone_masked ?? "—"} />
            <Field label="项目" value={detail.project_name ?? "—"} />
            <Field label="房号" value={`${detail.building ?? ""}${detail.room ?? ""}`} />
            <Field label="欠费金额" value={detail.amount_owed ? `¥${detail.amount_owed}` : "—"} />
            <Field label="本金" value={detail.principal_amount ? `¥${detail.principal_amount}` : "—"} />
            <Field label="滞纳金" value={detail.late_fee_amount ? `¥${detail.late_fee_amount}` : "—"} />
            <Field label="逾期" value={detail.months_overdue != null ? `${detail.months_overdue} 月` : "—"} />
            <Field label="案件阶段" value={detail.stage ?? "—"} />
            <Field label="最近跟进" value={detail.last_contact_at ? detail.last_contact_at.slice(0, 10) : "—"} />
            <Field label="优先级分" value={detail.priority_score ?? "—"} />
            <Field label="通话次数" value={detail.call_count ?? 0} />
          </div>
        </div>
      </div>

      {/* 发起转化请求 Dialog */}
      {dialogOpen && (
        <div className="modal-overlay" onClick={handleDialogClose}>
          <div className="ds-modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">发起法务转化请求</span>
              <button type="button" className="modal-close" onClick={handleDialogClose}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label className="form-label">申请理由 *</label>
                <textarea
                  className="form-control"
                  rows={4}
                  maxLength={2000}
                  placeholder="请说明转法务的理由（如逾期时长、催收经过等）"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  style={{ width: "100%", resize: "vertical" }}
                />
              </div>
              {err && (
                <div style={{ color: "var(--color-danger)", fontSize: 13 }}>{err}</div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="ds-btn ds-btn-secondary" onClick={handleDialogClose}>
                取消
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                disabled={isPending}
                onClick={handleSubmit}
              >
                {isPending ? "提交中…" : "提交"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
