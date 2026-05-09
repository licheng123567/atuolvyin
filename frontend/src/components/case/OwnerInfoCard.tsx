// v1.6.6 — 业主信息卡（admin / agent 详情页 + 催收员工作台 col-2 共用）
// 1:1 还原图 1：业主信息 / 累计欠费 hero / 物业费/违约金/欠费总额 三栏 / 欠费理由 / 标签
import type { CaseDetailResponse } from "../../types/case";
import { STAGE_BADGE_CLASS, STAGE_LABELS } from "./constants";

interface Props {
  detail: CaseDetailResponse;
  /** compact = true 用于工作台 240px 列：缩小字号、3 卡片改 2 行布局 */
  compact?: boolean;
}

export function OwnerInfoCard({ detail, compact = false }: Props) {
  const room = detail.owner.building && detail.owner.room
    ? `${detail.owner.building}${detail.owner.room}`
    : detail.owner.building ?? detail.owner.room ?? "—";
  const amountOwed = detail.amount_owed ? Number(detail.amount_owed) : 0;
  const monthsOverdue = detail.months_overdue ?? 0;
  const principalAmount = detail.principal_amount ? Number(detail.principal_amount) : 0;
  const lateFeeAmount = detail.late_fee_amount ? Number(detail.late_fee_amount) : 0;
  const hasBillBreakdown = principalAmount > 0 || lateFeeAmount > 0;

  // compact 模式各种字号 / 间距收紧
  const avatarSize = compact ? 40 : 48;
  const nameSize = compact ? 14 : 16;
  const heroAmountSize = compact ? 24 : 32;

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

        {/* info-grid：手机号 / 项目 / 负责员工 */}
        <div
          className="info-grid"
          style={{
            marginBottom: compact ? 12 : 16,
            ...(compact ? { gridTemplateColumns: "1fr 1fr" } : undefined),
          }}
        >
          <div className="info-item">
            <div className="info-label">手机号</div>
            <div className="info-value" style={{ fontFamily: "var(--font-mono, monospace)" }}>
              {detail.owner.phone_masked}
            </div>
          </div>
          <div className="info-item">
            <div className="info-label">所属项目</div>
            <div className="info-value">{detail.project_name ?? "—"}</div>
          </div>
          {!compact && (
            <div className="info-item">
              <div className="info-label">负责员工</div>
              <div className="info-value">
                <AssignedBadge assignedTo={detail.assigned_to} role={detail.assigned_role} />
              </div>
            </div>
          )}
        </div>

        {compact && (
          <div style={{ marginBottom: 12 }}>
            <div className="info-label" style={{ marginBottom: 4 }}>负责员工</div>
            <AssignedBadge assignedTo={detail.assigned_to} role={detail.assigned_role} />
          </div>
        )}

        {/* 累计欠费 hero */}
        {amountOwed > 0 && (
          <div style={{
            background: "#fef2f2", borderRadius: 8,
            padding: compact ? 12 : 16, textAlign: "center",
            marginBottom: compact ? 12 : 16,
          }}>
            <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>累计欠费</div>
            <div style={{ fontSize: heroAmountSize, fontWeight: 700, color: "#e02424" }}>
              ¥{amountOwed.toLocaleString()}
            </div>
            {monthsOverdue > 0 && (
              <div style={{ fontSize: 12, color: "#6b7280" }}>共 {monthsOverdue} 个月</div>
            )}
          </div>
        )}

        {/* 账单期 + 物业费/违约金/欠费总额 三栏 */}
        {hasBillBreakdown && (
          <div style={{ marginBottom: compact ? 12 : 16 }}>
            {(detail.bill_period_start || detail.bill_period_end) && (
              <div style={{
                fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 8,
              }}>
                账单期：{detail.bill_period_start ?? "—"} ~ {detail.bill_period_end ?? "—"}
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
      </div>
    </div>
  );
}

function AssignedBadge({ assignedTo, role }: { assignedTo: number | null; role?: string | null }) {
  if (!assignedTo) return <span className="ds-badge ds-badge-gray">未分配</span>;
  if (role === "agent_external") return <span className="ds-badge ds-badge-purple">服务商负责</span>;
  if (role === "agent_internal") return <span className="ds-badge ds-badge-green">内勤负责</span>;
  return <>员工 #{assignedTo}</>;
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
