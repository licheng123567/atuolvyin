// v0.8.0 Wave C — 物业 admin/PM/supervisor 案件详情右栏小卡片
//
// 数据源:GET /api/v1/admin/cases/{case_id}/evidence-status
//
// 与法务侧 EvidenceStatusPanel.tsx 互补:
//   - 法务面板:完整 4 类细分 + 法律效力提示 + 「打包上链 ¥99」按钮
//   - 本卡片:仅展示数量(本地哈希 / 司法链 / 待上链) + 单一 CTA
//
// CTA 逻辑:
//   - 已转法务 → 「查看证据中心 →」(跳 /legal/cases/{lc_id})
//   - 未转法务 → 「移交法务时一并上链」(展示性,真正触发在 ConvertToLegalModal)
//
// 显示规则:
//   - has_strong=true 卡片左边框绿色,顶部「✅ 强证据」
//   - has_strong=false & pending_count>0 卡片左边框黄色,顶部「🟡 待上链 N 件」
//   - has_strong=false & pending_count=0 卡片左边框灰色,顶部「⚠️ 仅本地哈希」
import { useCustom, useGo } from "@refinedev/core";
import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

interface EvidenceStatusResp {
  case_id: number;
  local_count: number;
  chain_count: number;
  pending_count: number;
  is_in_legal: boolean;
  legal_case_id: number | null;
  has_strong: boolean;
}

interface EvidenceStatusBadgeProps {
  caseId: number;
  /** 若已转法务,可选直接传 legal_case_id 跳过查 — 但本组件会自己查所以一般不传 */
  legalCaseIdHint?: number | null;
}

export function EvidenceStatusBadge({ caseId }: EvidenceStatusBadgeProps) {
  const go = useGo();
  const { query } = useCustom<EvidenceStatusResp>({
    url: `admin/cases/${caseId}/evidence-status`,
    method: "get",
  });

  const data = query.data?.data;

  if (query.isLoading || !data) {
    return (
      <div className="ds-card" style={{ padding: 12 }}>
        <div
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            color: "#374151",
            marginBottom: 8,
          }}
        >
          证据状态
        </div>
        <div style={{ fontSize: 12, color: "#9CA3AF" }}>加载中…</div>
      </div>
    );
  }

  // 选三态外观
  const variant: "strong" | "pending" | "weak" = data.has_strong
    ? "strong"
    : data.pending_count > 0
      ? "pending"
      : "weak";

  const accent =
    variant === "strong"
      ? "#10B981"  // green
      : variant === "pending"
        ? "#F59E0B"  // amber
        : "#9CA3AF"; // gray

  const Icon =
    variant === "strong"
      ? ShieldCheck
      : variant === "pending"
        ? ShieldAlert
        : ShieldQuestion;

  const headerText =
    variant === "strong"
      ? "已强化为司法链证据"
      : variant === "pending"
        ? `待上链 ${data.pending_count} 件`
        : "仅本地哈希(弱证据)";

  return (
    <div
      className="ds-card"
      style={{
        padding: 12,
        borderLeft: `3px solid ${accent}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12.5,
          fontWeight: 700,
          color: "#374151",
          marginBottom: 10,
        }}
      >
        <Icon className="w-3.5 h-3.5" style={{ color: accent }} />
        证据状态
      </div>

      {/* 顶部标题 — 颜色匹配状态 */}
      <div
        style={{
          fontSize: 11.5,
          fontWeight: 600,
          color: accent,
          marginBottom: 10,
        }}
      >
        {headerText}
      </div>

      {/* 数量明细 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <RowItem label="本地哈希" value={data.local_count} suffix="件" tone="ok" />
        <RowItem
          label="司法链"
          value={data.chain_count}
          suffix="件"
          tone={data.chain_count > 0 ? "ok" : "warn"}
        />
        {data.pending_count > 0 && (
          <RowItem
            label="待上链"
            value={data.pending_count}
            suffix="件"
            tone="pending"
          />
        )}
      </div>

      {/* CTA */}
      <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px dashed #E5E7EB" }}>
        {data.is_in_legal && data.legal_case_id ? (
          <button
            type="button"
            onClick={() =>
              go({ to: `/legal/cases/${data.legal_case_id}`, type: "push" })
            }
            className="ds-btn ds-btn-secondary ds-btn-sm"
            style={{ width: "100%", justifyContent: "center", fontSize: 11.5 }}
          >
            查看证据中心 →
          </button>
        ) : (
          <div
            style={{
              fontSize: 11,
              color: "#6B7280",
              lineHeight: 1.5,
            }}
          >
            {variant === "weak" ? (
              <>
                ⚠️ 当前为本地哈希,法庭可被质疑。
                <br />
                <span style={{ color: "#374151", fontWeight: 600 }}>
                  移交法务时一并上链(¥99/案)
                </span>
                — 升级为司法链强证据。
              </>
            ) : variant === "pending" ? (
              <>
                L2 风险事件已标记待上链,转法务时统一提交,零费用追加。
              </>
            ) : (
              <>已是司法链证据,律师函可附 tx_hash 作证据链。</>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function RowItem({
  label,
  value,
  suffix,
  tone,
}: {
  label: string;
  value: number;
  suffix: string;
  tone: "ok" | "warn" | "pending";
}) {
  const valueColor =
    tone === "ok"
      ? "#10B981"
      : tone === "pending"
        ? "#F59E0B"
        : "#9CA3AF";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        fontSize: 11.5,
      }}
    >
      <span style={{ color: "#6B7280" }}>{label}</span>
      <span style={{ fontWeight: 600, color: valueColor }}>
        {value} {suffix}
      </span>
    </div>
  );
}

export default EvidenceStatusBadge;
