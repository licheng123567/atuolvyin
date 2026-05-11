// v1.6.6 — 业主信息卡（admin / agent 详情页 + 催收员工作台 col-2 共用）
// v1.8.0 — 信息层级重构：
//   - 去「所属项目」「负责员工」「累计欠费 hero」（数据冗余）
//   - 「账单期」→「欠款月份：YYYY-MM 至 YYYY-MM（共 X 个月）」（更直观）
//   - 加 3 列统计卡片（联系/承诺/工单次数）
//   - mode="workstation" 时挂「最近通话记录」accordion
import type { CaseDetailResponse } from "../../types/case";
import { STAGE_BADGE_CLASS, STAGE_LABELS } from "./constants";
import { RecentCallsAccordion } from "./RecentCallsAccordion";

interface Props {
  detail: CaseDetailResponse;
  /** v1.8.0 — workstation = 催收员工作台 col-2（紧凑 + 挂最近通话）；detail = 案件详情页 */
  mode?: "workstation" | "detail";
  /** @deprecated v1.6 — compact 旧 prop，保留兼容；workstation mode 自带 compact */
  compact?: boolean;
}

export function OwnerInfoCard({ detail, mode = "detail", compact: compatCompact = false }: Props) {
  const compact = mode === "workstation" || compatCompact;
  const room = detail.owner.building && detail.owner.room
    ? `${detail.owner.building}${detail.owner.room}`
    : detail.owner.building ?? detail.owner.room ?? "—";
  const amountOwed = detail.amount_owed ? Number(detail.amount_owed) : 0;
  const monthsOverdue = detail.months_overdue ?? 0;
  const principalAmount = detail.principal_amount ? Number(detail.principal_amount) : 0;
  const lateFeeAmount = detail.late_fee_amount ? Number(detail.late_fee_amount) : 0;
  const hasBillBreakdown = principalAmount > 0 || lateFeeAmount > 0 || amountOwed > 0;
  const billPeriodLabel = formatBillPeriod(detail.bill_period_start, detail.bill_period_end, monthsOverdue);

  const avatarSize = compact ? 40 : 48;
  const nameSize = compact ? 14 : 16;

  return (
    <div className="ds-card section-gap">
      <div className="card-header">
        <span className="card-title">业主信息</span>
        <span className={STAGE_BADGE_CLASS[detail.stage] ?? "ds-badge ds-badge-gray"}>
          {STAGE_LABELS[detail.stage] ?? detail.stage}
        </span>
      </div>
      <div className="card-body">
        {/* 头像 + 名字 */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: compact ? 12 : 16 }}>
          <div style={{
            width: avatarSize, height: avatarSize, borderRadius: "50%",
            background: "#dbeafe", color: "#1A56DB",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: compact ? 16 : 20, fontWeight: 700, flexShrink: 0,
          }}>
            {detail.owner.name[0]}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: nameSize, fontWeight: 700 }}>{detail.owner.name}</div>
            <div style={{ fontSize: 13, color: "#6b7280" }}>{room}</div>
          </div>
        </div>

        {/* 手机号（单独一行，去项目/负责员工） */}
        <div style={{ marginBottom: compact ? 12 : 16 }}>
          <div className="info-label">手机号</div>
          <div className="info-value" style={{ fontFamily: "var(--font-mono, monospace)" }}>
            {detail.owner.phone_masked}
          </div>
        </div>

        {/* v1.8.0 — 3 列统计卡片：联系 / 承诺 / 工单 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 8,
            marginBottom: compact ? 12 : 16,
          }}
        >
          <StatCell label="联系次数" value={detail.monthly_contact_count ?? 0} />
          <StatCell label="承诺次数" value={detail.promise_count ?? 0} />
          <StatCell label="工单数量" value={detail.workorder_count ?? 0} />
        </div>

        {/* 欠款月份 + 物业费/违约金/欠费总额 三栏 */}
        {hasBillBreakdown && (
          <div style={{ marginBottom: compact ? 12 : 16 }}>
            {billPeriodLabel && (
              <div style={{
                fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 8,
              }}>
                欠款月份：{billPeriodLabel}
              </div>
            )}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: compact ? 6 : 8,
            }}>
              <BillCell label="物业费" value={principalAmount} bg="#f9fafb" labelColor="var(--color-neutral-500)" valueColor="#0f172a" />
              <BillCell label="违约金" value={lateFeeAmount} bg="#fef3c7" labelColor="#92400e" valueColor="#92400e" />
              <BillCell label="欠费总额" value={amountOwed} bg="#fee2e2" labelColor="#991b1b" valueColor="#991b1b" bold />
            </div>
          </div>
        )}

        {/* 欠费理由 */}
        {detail.arrears_reason && (
          <div style={{
            marginBottom: compact ? 12 : 16,
            padding: "10px 12px",
            background: "#fffbeb", borderRadius: 6, border: "1px solid #fde68a",
          }}>
            <div style={{ fontSize: 11, color: "#92400e", marginBottom: 2 }}>欠费理由</div>
            <div style={{ fontSize: 13, color: "#78350f" }}>{detail.arrears_reason}</div>
          </div>
        )}

        {/* tags */}
        <div style={{
          display: "flex", gap: 8, marginTop: compact ? 8 : 16, flexWrap: "wrap",
        }}>
          {detail.owner.do_not_call && (
            <span className="ds-badge ds-badge-red">免打扰</span>
          )}
          {monthsOverdue >= 12 && (
            <span className="ds-badge ds-badge-orange">长期欠费</span>
          )}
          {detail.stage === "promised" && (
            <span className="ds-badge ds-badge-blue">已承诺</span>
          )}
        </div>

        {/* v1.8.0 — workstation mode 挂「最近通话记录」accordion，详情页不挂（中栏 ActivityTimeline 已有） */}
        {mode === "workstation" && (
          <div style={{ marginTop: 16 }}>
            <RecentCallsAccordion calls={detail.calls} />
          </div>
        )}
      </div>
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      padding: "10px 8px",
      background: "#f9fafb",
      borderRadius: 6,
      textAlign: "center",
      border: "1px solid var(--color-neutral-200)",
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#0f172a", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function BillCell({ label, value, bg, labelColor, valueColor, bold }: {
  label: string;
  value: number;
  bg: string;
  labelColor: string;
  valueColor: string;
  bold?: boolean;
}) {
  return (
    <div style={{ padding: 10, background: bg, borderRadius: 6, textAlign: "center" }}>
      <div style={{ fontSize: 11, color: labelColor }}>{label}</div>
      <div style={{
        fontSize: 16, fontWeight: bold ? 700 : 600, marginTop: 2, color: valueColor,
      }}>
        ¥{value.toLocaleString()}
      </div>
    </div>
  );
}

/** 把 bill_period_start/end + months_overdue 转成「YYYY-MM 至 YYYY-MM（共 X 个月）」 */
function formatBillPeriod(
  start: string | null | undefined,
  end: string | null | undefined,
  months: number,
): string | null {
  if (!start && !end) return months > 0 ? `共 ${months} 个月` : null;
  const startYM = start ? start.slice(0, 7) : "—";
  const endYM = end ? end.slice(0, 7) : "—";
  const monthsText = months > 0 ? `（共 ${months} 个月）` : "";
  return `${startYM} 至 ${endYM}${monthsText}`;
}
