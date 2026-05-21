// v0.7.0 — 抽离 PmAlertsSection 到共享组件
//
// 原由 pages/pm/dashboard.tsx 内部定义,现在 PM dashboard 和服务商 admin
// dashboard 都用同一份(后端 GET /pm/dashboard/alerts 守卫 admin / project_manager)。
//
// 5 类提醒:
//   pending_approval_backlog / promise_overdue_uncalled / agent_anomaly
//   / cost_warning / case_stage_stuck
import { useCustom } from "@refinedev/core";
import { AlertTriangle, BellRing } from "lucide-react";
import { Link } from "react-router-dom";

interface PMAlertCard {
  key: string;
  label: string;
  count: number;
  severity: "info" | "warn" | "critical";
  detail_path: string | null;
}

interface PMAlertsResp {
  scope: "property" | "provider";
  alerts: PMAlertCard[];
}

const SEVERITY_BG: Record<PMAlertCard["severity"], string> = {
  info: "#f3f4f6",
  warn: "#fef3c7",
  critical: "#fee2e2",
};
const SEVERITY_COLOR: Record<PMAlertCard["severity"], string> = {
  info: "#6b7280",
  warn: "#c2410c",
  critical: "#dc2626",
};

export function PmAlertsSection() {
  const { query } = useCustom<PMAlertsResp>({
    url: "pm/dashboard/alerts",
    method: "get",
    queryOptions: { refetchInterval: 5 * 60 * 1000 },
  });
  const data = query.data?.data;

  if (query.isLoading) {
    return (
      <div
        style={{
          padding: 16, background: "white", borderRadius: 8,
          border: "1px solid #e5e7eb", fontSize: 13, color: "#6b7280",
        }}
      >
        加载运营提醒…
      </div>
    );
  }
  if (!data) return null;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        <BellRing className="w-4 h-4" style={{ color: "#c2410c" }} />
        <strong style={{ fontSize: 14, color: "#111827" }}>运营提醒</strong>
        <span style={{ fontSize: 11, color: "#6b7280" }}>
          5 分钟自动刷新 · 点击卡片跳详情页处理
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: 12,
        }}
      >
        {data.alerts.map((a) => {
          const inner = (
            <div
              key={a.key}
              style={{
                background: a.count > 0 ? SEVERITY_BG[a.severity] : "white",
                border: `1px solid ${a.count > 0 ? SEVERITY_COLOR[a.severity] + "40" : "#e5e7eb"}`,
                borderRadius: 8,
                padding: 12,
                cursor: a.detail_path ? "pointer" : "default",
                transition: "transform 0.1s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                {a.severity === "critical" && (
                  <AlertTriangle
                    className="w-3.5 h-3.5"
                    style={{ color: SEVERITY_COLOR.critical }}
                  />
                )}
                <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>
                  {a.label}
                </span>
              </div>
              <div
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  color: a.count > 0 ? SEVERITY_COLOR[a.severity] : "#9ca3af",
                  lineHeight: 1,
                }}
              >
                {a.count}
              </div>
              {a.detail_path && a.count > 0 && (
                <div
                  style={{
                    fontSize: 11,
                    color: SEVERITY_COLOR[a.severity],
                    marginTop: 6,
                  }}
                >
                  点击查看 →
                </div>
              )}
            </div>
          );
          return a.detail_path && a.count > 0 ? (
            <Link key={a.key} to={a.detail_path} style={{ textDecoration: "none" }}>
              {inner}
            </Link>
          ) : (
            <div key={a.key}>{inner}</div>
          );
        })}
      </div>
    </div>
  );
}

export default PmAlertsSection;
