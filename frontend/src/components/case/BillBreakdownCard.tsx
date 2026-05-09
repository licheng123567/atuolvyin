// v1.6.9 — 欠费明细卡（admin / supervisor / agent 案件详情共用）
// 显示账单期 + 物业费/违约金/欠费总额三栏，源自 case 导入时录入的 principal_amount + late_fee_amount + amount_owed
import type { CaseDetailResponse } from "../../types/case";

interface Props {
  detail: CaseDetailResponse;
  compact?: boolean;
}

export function BillBreakdownCard({ detail, compact = false }: Props) {
  const principal = detail.principal_amount ? Number(detail.principal_amount) : null;
  const lateFee = detail.late_fee_amount ? Number(detail.late_fee_amount) : null;
  const total = detail.amount_owed ? Number(detail.amount_owed) : 0;

  // 既无账单期也无金额拆分 → 不展示
  const hasBreakdown = principal != null || lateFee != null;
  const hasPeriod = !!(detail.bill_period_start || detail.bill_period_end);
  if (!hasBreakdown && !hasPeriod && total === 0) return null;

  const fmt = (n: number) =>
    `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;

  return (
    <div className="ds-card section-gap">
      <div className="card-header">
        <span className="card-title">💰 欠费明细</span>
        {hasPeriod && (
          <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
            账单期 {detail.bill_period_start ?? "—"} ~ {detail.bill_period_end ?? "—"}
          </span>
        )}
      </div>
      <div className="card-body">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: compact ? "1fr" : "repeat(3, 1fr)",
            gap: compact ? 8 : 12,
          }}
        >
          <div style={{ padding: 10, background: "#f9fafb", borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>物业费</div>
            <div style={{ fontSize: compact ? 15 : 18, fontWeight: 600, marginTop: 2 }}>
              {principal != null ? fmt(principal) : "—"}
            </div>
          </div>
          <div style={{ padding: 10, background: "#fef3c7", borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: "#92400e" }}>违约金</div>
            <div
              style={{
                fontSize: compact ? 15 : 18,
                fontWeight: 600,
                marginTop: 2,
                color: "#92400e",
              }}
            >
              {lateFee != null ? fmt(lateFee) : "—"}
            </div>
          </div>
          <div style={{ padding: 10, background: "#fee2e2", borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: "#991b1b" }}>欠费总额</div>
            <div
              style={{
                fontSize: compact ? 15 : 18,
                fontWeight: 700,
                marginTop: 2,
                color: "#991b1b",
              }}
            >
              {fmt(total)}
            </div>
          </div>
        </div>
        {!hasBreakdown && total > 0 && (
          <div
            style={{
              marginTop: 8,
              fontSize: 11,
              color: "var(--color-neutral-500)",
            }}
          >
            ⓘ 未录入物业费 / 违约金拆分，仅显示欠费总额
          </div>
        )}
      </div>
    </div>
  );
}
