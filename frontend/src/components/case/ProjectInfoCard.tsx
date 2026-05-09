// v1.6.6 — 项目基本情况卡（admin / agent 详情页 + 催收员工作台 col-2 共用）
// 1:1 还原图 1：项目基本情况 + 服务团队（电话团队 / 法务团队）
import { Scale } from "lucide-react";
import type { CaseDetailResponse } from "../../types/case";
import { CHARGE_PERIOD_LABELS, CONTRACT_TYPE_LABELS, legalStatusLabel } from "./constants";

interface Props {
  detail: CaseDetailResponse;
  compact?: boolean;
}

export function ProjectInfoCard({ detail, compact = false }: Props) {
  const projectInfo = detail.project_info;
  // 没有项目信息也不展示
  if (!projectInfo && !detail.calling_provider_name && !detail.legal_law_firm_name) {
    return null;
  }

  return (
    <div className="ds-card section-gap" style={{ borderLeft: "3px solid #6366f1" }}>
      <div className="card-header">
        <span className="card-title">📁 项目基本情况</span>
        {projectInfo?.name && (
          <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>
            {projectInfo.name}
          </span>
        )}
      </div>
      <div className="card-body">
        {projectInfo && (
          <div
            className="info-grid"
            style={compact ? { gridTemplateColumns: "1fr" } : undefined}
          >
            {projectInfo.charge_rate_text && (
              <div className="info-item" style={compact ? undefined : { gridColumn: "span 2" }}>
                <div className="info-label">收费标准</div>
                <div className="info-value" style={{ whiteSpace: "pre-wrap" }}>
                  {projectInfo.charge_rate_text}
                </div>
              </div>
            )}
            {projectInfo.charge_period && (
              <div className="info-item">
                <div className="info-label">收费周期</div>
                <div className="info-value">
                  {CHARGE_PERIOD_LABELS[projectInfo.charge_period] ?? projectInfo.charge_period}
                </div>
              </div>
            )}
            {projectInfo.contract_type && (
              <div className="info-item">
                <div className="info-label">合同类型</div>
                <div className="info-value">
                  {CONTRACT_TYPE_LABELS[projectInfo.contract_type] ?? projectInfo.contract_type}
                </div>
              </div>
            )}
            {/* compact 模式下 合同期 / 合同附件 / 收费备注 折叠（详情页看完整）*/}
            {!compact && (projectInfo.contract_start_date || projectInfo.contract_end_date) && (
              <div className="info-item" style={{ gridColumn: "span 2" }}>
                <div className="info-label">合同期</div>
                <div className="info-value">
                  {projectInfo.contract_start_date ?? "—"} ~ {projectInfo.contract_end_date ?? "—"}
                </div>
              </div>
            )}
            {!compact && projectInfo.contract_attachment_key && (
              <div className="info-item" style={{ gridColumn: "span 2" }}>
                <div className="info-label">合同附件</div>
                <div className="info-value">
                  📎 {projectInfo.contract_attachment_filename ?? "已上传"}
                </div>
              </div>
            )}
            {!compact && projectInfo.charge_notes && (
              <div className="info-item" style={{ gridColumn: "span 2" }}>
                <div className="info-label">收费备注</div>
                <div className="info-value" style={{ whiteSpace: "pre-wrap" }}>
                  {projectInfo.charge_notes}
                </div>
              </div>
            )}
            {compact && (projectInfo.contract_start_date || projectInfo.contract_end_date || projectInfo.charge_notes) && (
              <div style={{ fontSize: 11, color: "var(--color-neutral-400)", marginTop: 4 }}>
                合同期 / 收费备注 见「详情」
              </div>
            )}
          </div>
        )}

        {/* 服务团队（电话团队 / 法务团队）*/}
        {(detail.calling_provider_name || detail.legal_law_firm_name) && (
          <div style={{ marginTop: projectInfo ? 16 : 0, paddingTop: projectInfo ? 12 : 0,
            borderTop: projectInfo ? "1px solid var(--color-neutral-100)" : undefined,
            display: "flex", flexDirection: "column", gap: 12,
          }}>
            <div>
              <div className="info-label">电话团队</div>
              <div className="info-value">
                {detail.calling_provider_name ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span className="ds-badge ds-badge-blue">服务商</span>
                    {detail.calling_provider_name}
                  </span>
                ) : (
                  <span style={{ color: "var(--color-neutral-500)" }}>物业自办（未签约服务商）</span>
                )}
              </div>
            </div>
            <div>
              <div className="info-label">法务团队</div>
              <div className="info-value">
                {detail.legal_law_firm_name ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <Scale className="w-3.5 h-3.5" style={{ color: "#7e3af2" }} />
                    <span>{detail.legal_law_firm_name}</span>
                    {detail.legal_lawyer_name && (
                      <span style={{ fontSize: 12, color: "#6b7280" }}>· {detail.legal_lawyer_name}</span>
                    )}
                    {detail.legal_order_status && (
                      <span className="ds-badge ds-badge-purple" style={{ fontSize: 11 }}>
                        {legalStatusLabel(detail.legal_order_status)}
                      </span>
                    )}
                  </span>
                ) : (
                  <span style={{ color: "var(--color-neutral-500)" }}>未转化法务</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
