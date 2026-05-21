// v0.7.0 — 抽离 PmAlertsSection 到共享组件
//
// 原由 pages/pm/dashboard.tsx 内部定义,现在 PM dashboard 和服务商 admin
// dashboard 都用同一份(后端 GET /pm/dashboard/alerts 守卫 admin / project_manager)。
//
// v0.9.0 — 卡片点击行为升级:不再 Link 直接跳管理页,而是右侧 Drawer
//   展开该类别明细列表(每行带「处理 →」一键跳详情)。
//
// 5 类提醒:
//   pending_approval_backlog / promise_overdue_uncalled / agent_anomaly
//   / cost_warning / case_stage_stuck
import { useCustom } from "@refinedev/core";
import { AlertTriangle, BellRing } from "lucide-react";
import { useState } from "react";
import { PmAlertDetailDrawer } from "./PmAlertDetailDrawer";

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
  // v0.9.0 — 点击卡片打开右侧明细 Drawer(代替原 Link 跳管理页)
  const [activeAlert, setActiveAlert] = useState<{
    key: string;
    label: string;
  } | null>(null);

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
          5 分钟自动刷新 · 点击卡片展开明细
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
          const clickable = a.count > 0;
          return (
            <button
              key={a.key}
              type="button"
              onClick={() =>
                clickable && setActiveAlert({ key: a.key, label: a.label })
              }
              disabled={!clickable}
              style={{
                background: a.count > 0 ? SEVERITY_BG[a.severity] : "white",
                border: `1px solid ${a.count > 0 ? SEVERITY_COLOR[a.severity] + "40" : "#e5e7eb"}`,
                borderRadius: 8,
                padding: 12,
                cursor: clickable ? "pointer" : "default",
                transition: "transform 0.1s, box-shadow 0.1s",
                textAlign: "left",
                width: "100%",
                font: "inherit",
                color: "inherit",
              }}
              onMouseEnter={(e) => {
                if (clickable) {
                  e.currentTarget.style.boxShadow = "0 2px 6px rgba(0,0,0,.08)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "none";
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
              {clickable && (
                <div
                  style={{
                    fontSize: 11,
                    color: SEVERITY_COLOR[a.severity],
                    marginTop: 6,
                  }}
                >
                  点击查看明细 →
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* v0.9.0 — 明细 Drawer */}
      {activeAlert && (
        <PmAlertDetailDrawer
          alertKey={activeAlert.key}
          alertLabel={activeAlert.label}
          onClose={() => setActiveAlert(null)}
        />
      )}
    </div>
  );
}

export default PmAlertsSection;
