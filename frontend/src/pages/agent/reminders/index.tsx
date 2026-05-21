// v0.6.0 — 催收员提醒中心
//
// 两个数据源:
// 1. /api/v1/users/me/notifications — 站内信(事件类硬通知,有读未读)
// 2. /api/v1/agent/me/reminders/synthetic — 软提醒(实时计算的状态,无读未读)
//
// 页面分两段:
//   顶部:三类软提醒(承诺即将到期 / 法务进度 / 案件 SLA 告警)
//   底部:近期站内信列表(可标记已读 / 全部已读)
import { useCustom, useCustomMutation } from "@refinedev/core";
import { AlertTriangle, Bell, CheckCheck, Clock, ScaleIcon } from "lucide-react";
import { ScrollText } from "lucide-react";
import { Link } from "react-router-dom";

interface PromiseDueItem {
  case_id: number;
  owner_name: string;
  building_room: string;
  promise_due_at: string;
  promise_amount: string | null;
  promise_content: string | null;
  hours_to_due: number;
}

interface LegalStatusItem {
  request_id: number;
  case_id: number;
  owner_name: string;
  status: string;
  reviewer_note: string | null;
  updated_at: string;
}

interface CaseSlaItem {
  case_id: number;
  owner_name: string;
  building_room: string;
  last_contact_at: string | null;
  days_stuck: number;
  amount_owed: string | null;
}

interface SyntheticResp {
  promise_due_soon: PromiseDueItem[];
  legal_status_changes: LegalStatusItem[];
  case_sla_warn: CaseSlaItem[];
}

interface NotifItem {
  id: number;
  event_type: string;
  severity: string;
  title: string;
  body: string;
  payload: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}

interface NotifResp {
  items: NotifItem[];
  total: number;
}

const LEGAL_STATUS_LABEL: Record<string, { label: string; color: string }> = {
  approved: { label: "已批准", color: "#15803d" },
  approved_pending_legal: { label: "已批·待法务接单", color: "#1d4ed8" },
  rejected: { label: "已驳回", color: "#dc2626" },
};

const SEVERITY_COLOR: Record<string, string> = {
  info: "#1d4ed8",
  warn: "#c2410c",
  critical: "#dc2626",
};

export function AgentRemindersPage() {
  // 软提醒(实时计算)
  const { query: synthQuery } = useCustom<SyntheticResp>({
    url: "agent/me/reminders/synthetic",
    method: "get",
    queryOptions: { refetchInterval: 60_000 },  // 1 分钟轮询
  });
  const synth = synthQuery.data?.data;

  // 站内信
  const { query: notifQuery } = useCustom<NotifResp>({
    url: "users/me/notifications",
    method: "get",
    config: { query: { limit: 50 } },
    queryOptions: { refetchInterval: 30_000 },
  });
  const notifs = notifQuery.data?.data?.items ?? [];

  const { mutate: markRead } = useCustomMutation();
  const { mutate: markAllRead, mutation: markAllMut } = useCustomMutation();
  const unreadCount = notifs.filter((n) => n.read_at === null).length;

  const handleMarkOne = (id: number) => {
    markRead(
      {
        url: `users/me/notifications/${id}/read`,
        method: "patch",
        values: {},
      },
      { onSuccess: () => void notifQuery.refetch() },
    );
  };

  const handleMarkAll = () => {
    markAllRead(
      {
        url: "users/me/notifications/read-all",
        method: "patch",
        values: {},
      },
      { onSuccess: () => void notifQuery.refetch() },
    );
  };

  const totalAlerts =
    (synth?.promise_due_soon.length ?? 0)
    + (synth?.legal_status_changes.length ?? 0)
    + (synth?.case_sla_warn.length ?? 0);

  return (
    <div style={{ padding: 16 }}>
      <div className="page-header" style={{ marginBottom: 12 }}>
        <div>
          <div className="page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Bell className="w-5 h-5" />
            提醒中心
            {totalAlerts > 0 && (
              <span
                style={{
                  fontSize: 12, padding: "2px 8px", borderRadius: 10,
                  background: "#fef3c7", color: "#78350f", fontWeight: 600,
                }}
              >
                {totalAlerts} 条待办
              </span>
            )}
            {unreadCount > 0 && (
              <span
                style={{
                  fontSize: 12, padding: "2px 8px", borderRadius: 10,
                  background: "#fee2e2", color: "#991b1b", fontWeight: 600,
                }}
              >
                {unreadCount} 未读
              </span>
            )}
          </div>
          <div className="page-subtitle">
            实时状态提醒(承诺到期 / 法务进度 / 案件超期)+ 督导/系统站内信
          </div>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            className="ds-btn ds-btn-secondary ds-btn-sm"
            onClick={handleMarkAll}
            disabled={markAllMut.isPending}
          >
            <CheckCheck className="w-3.5 h-3.5" />
            全部标为已读
          </button>
        )}
      </div>

      {/* 软提醒 3 类 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, marginBottom: 16 }}>
        <ReminderGroup
          title="即将到期承诺"
          subtitle="未来 72 小时内业主承诺缴费的案件"
          icon={<Clock className="w-4 h-4" style={{ color: "#c2410c" }} />}
          headerColor="#c2410c"
          isLoading={synthQuery.isLoading}
          isEmpty={!synth || synth.promise_due_soon.length === 0}
          emptyText="暂无即将到期的承诺 — 继续保持节奏"
        >
          {synth?.promise_due_soon.map((p) => (
            <Link
              key={p.case_id}
              to={`/agent/cases/${p.case_id}`}
              style={{
                display: "block", padding: "8px 12px", borderRadius: 6,
                border: "1px solid #fde68a", background: "#fffbeb",
                marginBottom: 6, textDecoration: "none", color: "inherit",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {p.owner_name} · {p.building_room}
                </span>
                <span style={{ fontSize: 11, color: "#c2410c", fontWeight: 600 }}>
                  {p.hours_to_due < 1
                    ? "1 小时内"
                    : `${Math.round(p.hours_to_due)} 小时后`}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                {p.promise_amount && (
                  <span>承诺 ¥{p.promise_amount}</span>
                )}
                {p.promise_content && (
                  <span style={{ marginLeft: 6 }}>· {p.promise_content}</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                到期 {new Date(p.promise_due_at).toLocaleString("zh-CN")}
              </div>
            </Link>
          ))}
        </ReminderGroup>

        <ReminderGroup
          title="法务申请进度"
          subtitle="近 7 天我提交的转法务申请最新状态"
          icon={<ScaleIcon className="w-4 h-4" style={{ color: "#7e3af2" }} />}
          headerColor="#7e3af2"
          isLoading={synthQuery.isLoading}
          isEmpty={!synth || synth.legal_status_changes.length === 0}
          emptyText="近 7 天无法务申请状态变化"
        >
          {synth?.legal_status_changes.map((l) => {
            const meta = LEGAL_STATUS_LABEL[l.status] ?? { label: l.status, color: "#6b7280" };
            return (
              <Link
                key={l.request_id}
                to={`/agent/cases/${l.case_id}`}
                style={{
                  display: "block", padding: "8px 12px", borderRadius: 6,
                  border: "1px solid #e9d5ff", background: "#faf5ff",
                  marginBottom: 6, textDecoration: "none", color: "inherit",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {l.owner_name} · 申请 #{l.request_id}
                  </span>
                  <span style={{ fontSize: 11, color: meta.color, fontWeight: 600 }}>
                    {meta.label}
                  </span>
                </div>
                {l.reviewer_note && (
                  <div style={{ fontSize: 12, color: "#6b7280", whiteSpace: "pre-wrap" }}>
                    {l.reviewer_note}
                  </div>
                )}
                <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                  {new Date(l.updated_at).toLocaleString("zh-CN")}
                </div>
              </Link>
            );
          })}
        </ReminderGroup>

        <ReminderGroup
          title="案件 SLA 告警"
          subtitle="停滞 ≥ 30 天的非终止案件 — 建议尽快推进或申请转法务"
          icon={<AlertTriangle className="w-4 h-4" style={{ color: "#dc2626" }} />}
          headerColor="#dc2626"
          isLoading={synthQuery.isLoading}
          isEmpty={!synth || synth.case_sla_warn.length === 0}
          emptyText="所有案件均在 30 天活跃窗口内"
        >
          {synth?.case_sla_warn.map((c) => (
            <Link
              key={c.case_id}
              to={`/agent/cases/${c.case_id}`}
              style={{
                display: "block", padding: "8px 12px", borderRadius: 6,
                border: "1px solid #fecaca", background: "#fef2f2",
                marginBottom: 6, textDecoration: "none", color: "inherit",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {c.owner_name} · {c.building_room}
                </span>
                <span style={{ fontSize: 11, color: "#dc2626", fontWeight: 600 }}>
                  停滞 {c.days_stuck} 天
                </span>
              </div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                {c.amount_owed && <span>欠 ¥{c.amount_owed}</span>}
                {c.last_contact_at && (
                  <span style={{ marginLeft: 6 }}>
                    · 上次接触 {new Date(c.last_contact_at).toLocaleDateString("zh-CN")}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </ReminderGroup>
      </div>

      {/* 站内信 */}
      <ReminderGroup
        title="近期站内信"
        subtitle="督导动作 / 工单 / 系统事件等通知"
        icon={<ScrollText className="w-4 h-4" style={{ color: "#1d4ed8" }} />}
        headerColor="#1d4ed8"
        isLoading={notifQuery.isLoading}
        isEmpty={notifs.length === 0}
        emptyText="近期无站内信"
      >
        {notifs.map((n) => (
          <div
            key={n.id}
            style={{
              display: "flex", gap: 8, padding: "8px 12px", borderRadius: 6,
              border: `1px solid ${n.read_at ? "#e5e7eb" : "#bfdbfe"}`,
              background: n.read_at ? "#ffffff" : "#eff6ff",
              marginBottom: 6,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <span
                  style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: SEVERITY_COLOR[n.severity] ?? "#6b7280",
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontWeight: 600, fontSize: 13 }}>{n.title}</span>
                <span style={{ fontSize: 11, color: "#9ca3af" }}>
                  {new Date(n.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "#374151", whiteSpace: "pre-wrap" }}>
                {n.body}
              </div>
            </div>
            {!n.read_at && (
              <button
                type="button"
                className="ds-btn ds-btn-ghost ds-btn-sm"
                style={{ alignSelf: "flex-start", fontSize: 11 }}
                onClick={() => handleMarkOne(n.id)}
              >
                标为已读
              </button>
            )}
          </div>
        ))}
      </ReminderGroup>
    </div>
  );
}

function ReminderGroup({
  title, subtitle, icon, headerColor,
  isLoading, isEmpty, emptyText, children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  headerColor: string;
  isLoading: boolean;
  isEmpty: boolean;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: "white",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        borderLeft: `3px solid ${headerColor}`,
        padding: 12,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        {icon}
        <strong style={{ fontSize: 14, color: "#111827" }}>{title}</strong>
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 10 }}>
        {subtitle}
      </div>
      {isLoading ? (
        <div style={{ padding: 12, textAlign: "center", fontSize: 12, color: "#9ca3af" }}>
          加载中…
        </div>
      ) : isEmpty ? (
        <div style={{ padding: 12, textAlign: "center", fontSize: 12, color: "#9ca3af" }}>
          {emptyText}
        </div>
      ) : (
        <div>{children}</div>
      )}
    </div>
  );
}

export default AgentRemindersPage;
