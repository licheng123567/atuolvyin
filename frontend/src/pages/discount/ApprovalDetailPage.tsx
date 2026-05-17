import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { STATUS_BADGES, STATUS_LABELS } from "./_mock";
import { useDiscountOffer } from "./api";
import { SourceBadge } from "./SourceBadge";

interface Props {
  backTo: string;
  approverRole: "supervisor" | "admin";
}

export function ApprovalDetailPage({ backTo, approverRole: _ }: Props) {
  const { id } = useParams<{ id: string }>();
  const offerId = Number(id);
  const { offer, isLoading, isError } = useDiscountOffer(offerId);

  if (isLoading) {
    return (
      <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载中…</div>
    );
  }

  if (isError || !offer) {
    return (
      <div style={{ padding: 24 }}>
        <Link to={backTo} style={{ color: "var(--color-neutral-500)", fontSize: 13 }}>
          <ArrowLeft size={14} style={{ display: "inline", verticalAlign: "middle" }} /> 返回审批列表
        </Link>
        <div className="ds-card" style={{ marginTop: 12 }}>
          <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>
            申请 #{id} 不存在或不属于本租户
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <Link to={backTo} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13, textDecoration: "none", marginBottom: 12 }}>
        <ArrowLeft size={14} /> 返回审批列表
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>减免申请 #{offer.id}</h1>
        <span className={STATUS_BADGES[offer.status]} style={{ fontSize: 12 }}>{STATUS_LABELS[offer.status]}</span>
      </div>

      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>申请详情</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 24px" }}>
            <Field label="案件" value={
              <Link to={`/supervisor/cases/${offer.case_id}`} style={{ color: "var(--color-primary)" }}>
                #{offer.case_id} · {offer.case_owner ?? "—"} / {offer.case_building ?? ""}
              </Link>
            } />
            <Field label="项目" value={offer.project_name ?? "—"} />
            <Field label="申请人" value={`${offer.applicant_name ?? "—"}（${offer.applicant_role === "agent" ? "催收员" : "督导"}）`} />
            <Field label="减免类型" value={offer.offer_type_label + (offer.installment_months ? `（${offer.installment_months} 期）` : "")} />
            <Field label="原欠费" value={`¥${Number(offer.original_amount).toLocaleString("zh-CN")}`} />
            <Field label="业主同意支付" value={<span style={{ fontWeight: 600 }}>¥{Number(offer.proposed_amount).toLocaleString("zh-CN")}</span>} />
            <Field label="折扣比例" value={
              <span style={{ fontWeight: 600 }}>{offer.discount_pct}%</span>
            } />
            <Field label="有效期至" value={offer.expires_at?.slice(0, 10) ?? "—"} />
            <Field label="来源" value={
              <SourceBadge providerId={offer.provider_id} providerName={offer.provider_name} />
            } />
          </div>

          <div style={{ marginTop: 16, padding: 12, background: "#f9fafb", borderRadius: 6 }}>
            <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 4 }}>申请理由</div>
            <div style={{ fontSize: 13.5, color: "#1f2937", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{offer.reason}</div>
          </div>

          {offer.rejected_reason && (
            <div style={{ marginTop: 12, padding: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 6 }}>
              <div style={{ fontSize: 12, color: "var(--color-danger)", marginBottom: 4, fontWeight: 600 }}>拒绝原因</div>
              <div style={{ fontSize: 13, color: "#1f2937" }}>{offer.rejected_reason}</div>
            </div>
          )}
        </div>
      </div>

      <div className="ds-card">
        <div className="card-body" style={{ padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>审批轨迹</div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13 }}>
            {offer.audit_trail.map((t, i) => (
              <li key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < offer.audit_trail.length - 1 ? "1px solid #f3f4f6" : "none" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-primary)", marginTop: 7, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13 }}>{t.action}</div>
                  <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 2 }}>{t.actor} · {t.time}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{value}</div>
    </div>
  );
}
