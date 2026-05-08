// 团队监控 — 1:1 还原 ui/supervisor.html#sv-team
// v1.5.7 — KPI 4 张 stat-card + 团队成员表
import { useState } from "react";

interface AgentRow {
  name: string;
  status: "in_call" | "idle" | "offline";
  status_label: string;
  status_badge: string;
  call_count: number;
  connect_count: number;
  promise_count: number;
  ai_adoption: number;
  private_pool: number;
  risk_label: string | null;
  risk_badge: string;
}

const MOCK_AGENTS: AgentRow[] = [
  { name: "李小红", status: "in_call", status_label: "通话中", status_badge: "ds-badge ds-badge-blue",
    call_count: 22, connect_count: 15, promise_count: 7, ai_adoption: 89, private_pool: 48,
    risk_label: "L2×1", risk_badge: "ds-badge ds-badge-red" },
  { name: "王芳芳", status: "in_call", status_label: "通话中", status_badge: "ds-badge ds-badge-blue",
    call_count: 18, connect_count: 12, promise_count: 5, ai_adoption: 76, private_pool: 39,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
  { name: "张建华", status: "idle", status_label: "空闲", status_badge: "ds-badge ds-badge-gray",
    call_count: 21, connect_count: 14, promise_count: 6, ai_adoption: 83, private_pool: 41,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
  { name: "陈明远", status: "idle", status_label: "空闲", status_badge: "ds-badge ds-badge-green",
    call_count: 18, connect_count: 11, promise_count: 4, ai_adoption: 72, private_pool: 55,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
  { name: "刘晓娟", status: "in_call", status_label: "通话中", status_badge: "ds-badge ds-badge-blue",
    call_count: 16, connect_count: 10, promise_count: 6, ai_adoption: 85, private_pool: 32,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
  { name: "周海燕", status: "idle", status_label: "空闲", status_badge: "ds-badge ds-badge-gray",
    call_count: 14, connect_count: 9, promise_count: 4, ai_adoption: 79, private_pool: 28,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
  { name: "赵志远", status: "in_call", status_label: "通话中", status_badge: "ds-badge ds-badge-blue",
    call_count: 13, connect_count: 8, promise_count: 3, ai_adoption: 68, private_pool: 24,
    risk_label: "L1×1", risk_badge: "ds-badge ds-badge-orange" },
  { name: "孙倩倩", status: "offline", status_label: "离线", status_badge: "ds-badge ds-badge-gray",
    call_count: 20, connect_count: 13, promise_count: 3, ai_adoption: 74, private_pool: 36,
    risk_label: null, risk_badge: "ds-badge ds-badge-gray" },
];

export function SupervisorTeamPerformancePage() {
  const [date] = useState(new Date().toISOString().slice(0, 10));
  const totalCalls = MOCK_AGENTS.reduce((s, a) => s + a.call_count, 0);
  const totalConnect = MOCK_AGENTS.reduce((s, a) => s + a.connect_count, 0);
  const totalPromise = MOCK_AGENTS.reduce((s, a) => s + a.promise_count, 0);
  const avgAdoption = Math.round(MOCK_AGENTS.reduce((s, a) => s + a.ai_adoption, 0) / MOCK_AGENTS.length);
  const connectRate = ((totalConnect / totalCalls) * 100).toFixed(1);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">团队监控</div>
          <div className="page-subtitle">今日团队整体绩效概览</div>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--color-neutral-500)" }}>统计日期：{date}</div>
      </div>

      <div className="kpi-grid">
        <StatCard label="今日总通话量" value={totalCalls} change="↑ 12% 较昨日" tone="up" />
        <StatCard label="接通率" value={`${connectRate}%`} change="↑ 3.1%" tone="up" />
        <StatCard label="今日承诺数" value={totalPromise} change="↑ 8 条" tone="up" />
        <StatCard label="平均 AI 采用率" value={`${avgAdoption}%`} change="↑ 5%" tone="up" />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>催收员</th>
              <th>今日状态</th>
              <th>通话次数</th>
              <th>接通次数</th>
              <th>承诺数</th>
              <th>AI 采用率</th>
              <th>私海数</th>
              <th>风险事件</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_AGENTS.map((a) => (
              <tr key={a.name}>
                <td><strong>{a.name}</strong></td>
                <td><span className={a.status_badge}>{a.status_label}</span></td>
                <td>{a.call_count}</td>
                <td>{a.connect_count}</td>
                <td>{a.promise_count}</td>
                <td>
                  {a.ai_adoption >= 80 ? (
                    <span style={{ color: "var(--color-success)", fontWeight: 600 }}>{a.ai_adoption}%</span>
                  ) : (
                    <span>{a.ai_adoption}%</span>
                  )}
                </td>
                <td>{a.private_pool}</td>
                <td>
                  {a.risk_label ? (
                    <span className={a.risk_badge} style={{ fontSize: 11 }}>{a.risk_label}</span>
                  ) : (
                    <span className="ds-badge ds-badge-gray" style={{ fontSize: 11 }}>无</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, change, tone }: { label: string; value: string | number; change: string; tone: "up" | "down" }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className={`stat-change ${tone}`}>{change}</div>
    </div>
  );
}
