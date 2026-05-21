// 督导工作台 — 1:1 还原 ui/supervisor.html#sv-workspace
// v1.5.7 — 含状态条 + 员工实时卡片 + 待复核/风控/话术效果/分钟趋势 4 大面板
import { AlertTriangle, BarChart2, Clock, MessageCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

interface AgentStatus {
  user_id: number;
  name: string;
  initial: string;
  state: "in_call" | "idle" | "offline" | "just_ended";
  duration?: string;
  contact_owner?: string;
  contact_room?: string;
  risk_level?: "L1" | "L2" | null;
  risk_keyword?: string;
  today_count?: number;
  last_owner?: string;
  last_minutes_ago?: number;
  project_name: string;
}

const MOCK_AGENTS: AgentStatus[] = [
  {
    user_id: 5, name: "李小红", initial: "李", state: "in_call",
    duration: "03:42", contact_owner: "张大伟", contact_room: "3-1201",
    risk_level: "L2", risk_keyword: "不想交",
    project_name: "金桂园 2026 年欠费催收",
  },
  {
    user_id: 6, name: "王芳芳", initial: "王", state: "in_call",
    duration: "01:18", contact_owner: "王建国", contact_room: "5-2201",
    risk_level: null,
    project_name: "金桂园 2026 年欠费催收",
  },
  {
    user_id: 7, name: "张建华", initial: "张", state: "just_ended",
    last_owner: "刘美华", last_minutes_ago: 2,
    project_name: "翠湖湾电梯专项整改",
  },
  {
    user_id: 8, name: "陈明远", initial: "陈", state: "idle",
    today_count: 18,
    project_name: "翠湖湾电梯专项整改",
  },
  {
    user_id: 9, name: "刘晓娟", initial: "刘", state: "in_call",
    duration: "00:45", contact_owner: "孙志远", contact_room: "4-1504",
    risk_level: null,
    project_name: "金桂园 2026 年欠费催收",
  },
];

const ALL_PROJECTS = [
  "全部项目",
  "金桂园 2026 年欠费催收",
  "翠湖湾电梯专项整改",
];

function nowTime(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export function SupervisorWorkspacePage() {
  const navigate = useNavigate();
  const [updateAt, setUpdateAt] = useState(nowTime());
  const [projectFilter, setProjectFilter] = useState<string>("全部项目");
  useEffect(() => {
    const t = setInterval(() => setUpdateAt(nowTime()), 1000);
    return () => clearInterval(t);
  }, []);

  const visibleAgents = projectFilter === "全部项目"
    ? MOCK_AGENTS
    : MOCK_AGENTS.filter((a) => a.project_name === projectFilter);
  const inCall = visibleAgents.filter((a) => a.state === "in_call").length;
  const idle = visibleAgents.filter((a) => a.state === "idle" || a.state === "just_ended").length;
  const offline = 3;
  const riskAlerts = visibleAgents.filter((a) => a.risk_level).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">督导工作台</div>
          <div className="page-subtitle">实时监控团队通话状态与风控事件</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            className="filter-select"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            aria-label="按项目筛选"
          >
            {ALL_PROJECTS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <span style={{ fontSize: 12.5, color: "var(--color-neutral-500)" }}>
            最后更新 {updateAt}
          </span>
        </div>
      </div>

      {/* 顶部状态条 */}
      <div className="status-bar">
        <div className="status-bar-item">
          <span className="dot-green" /> 通话中 <strong>{inCall}人</strong>
        </div>
        <div className="status-bar-item">
          <span className="dot-green" /> 空闲 <strong>{idle}人</strong>
        </div>
        <div className="status-bar-item">
          <span className="dot-gray" /> 离线 <strong>{offline}人</strong>
        </div>
        {riskAlerts > 0 && (
          <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
            <span className="dot-red" /> ⚠ 风控告警 <strong>{riskAlerts}条</strong>
          </div>
        )}
      </div>

      <div className="workspace-grid">
        {/* 左：员工实时状态 */}
        <div>
          <div className="section-subtitle">
            员工实时状态
            {projectFilter !== "全部项目" && (
              <span style={{ marginLeft: 8, fontSize: 12, color: "var(--color-primary)", fontWeight: 400 }}>
                · 仅显示「{projectFilter}」项目
              </span>
            )}
          </div>
          {visibleAgents.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)", background: "white", border: "1px solid var(--color-neutral-200)", borderRadius: 8 }}>
              该项目当前无活跃员工
            </div>
          ) : visibleAgents.map((a) => (
            <AgentCard key={a.user_id} agent={a} />
          ))}
        </div>

        {/* 右：4 个 panel */}
        <div>
          <div className="section-subtitle">关键提醒</div>
          <PanelAlert
            title="待复核"
            count={3}
            desc="有 3 条通话等待人工质检复核，其中含 1 条说话人异常标注。"
            onAction={() => navigate("/supervisor/reviews")}
          />
          <PanelRisk
            onView={() => navigate("/supervisor/risk-events")}
          />
          <PanelStat
            title="今日话术推送效果"
            value="82%"
            delta="↑5%"
            label="团队采用率"
            barPct={82}
            footer="今日推送话术 34 条，催收员采用 28 条"
            icon={<MessageCircle className="w-4 h-4" />}
          />
          <PanelMinutes />
        </div>
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentStatus }) {
  const navigate = useNavigate();
  const isRiskL2 = agent.risk_level === "L2";
  const isRiskL1 = agent.risk_level === "L1";
  const cardCls = `agent-card${isRiskL2 ? " risk-l2" : isRiskL1 ? " risk-l1" : ""}`;
  const avatarTone =
    agent.risk_level === "L2"
      ? "tone-danger"
      : agent.state === "idle"
        ? "tone-success"
        : agent.state === "just_ended"
          ? "tone-neutral"
          : "";

  return (
    <div className={cardCls}>
      <div className={`agent-avatar ${avatarTone}`}>{agent.initial}</div>
      <div className="agent-info">
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className="agent-name">{agent.name}</span>
          {agent.state === "in_call" && <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>IN_CALL</span>}
          {agent.state === "idle" && <span className="ds-badge ds-badge-green" style={{ fontSize: 11 }}>IDLE</span>}
          {agent.state === "just_ended" && <span className="ds-badge ds-badge-gray" style={{ fontSize: 11 }}>刚挂断</span>}
          {agent.duration && <span className="agent-timer">{agent.duration}</span>}
          {agent.last_minutes_ago !== undefined && (
            <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>
              {agent.last_minutes_ago}分钟前
            </span>
          )}
        </div>
        {agent.contact_owner && (
          <div className="agent-detail">
            对方：{agent.contact_owner} / {agent.contact_room}
            <span style={{ marginLeft: 8, color: "var(--color-primary)", fontSize: 11 }}>
              📁 {agent.project_name}
            </span>
          </div>
        )}
        {agent.last_owner && <div className="agent-detail">上通电话：{agent.last_owner}</div>}
        {agent.today_count !== undefined && (
          <div className="agent-detail">今日已完成 {agent.today_count} 通</div>
        )}
        {agent.risk_level && (
          <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
            <span
              className={`ds-badge ${agent.risk_level === "L2" ? "ds-badge-red" : "ds-badge-orange"}`}
              style={{ fontSize: 11 }}
            >
              风险 {agent.risk_level}
            </span>
            {agent.risk_keyword && (
              <span style={{ fontSize: 12, color: "var(--color-danger)" }}>
                检测到"{agent.risk_keyword}"
              </span>
            )}
          </div>
        )}
      </div>
      <div className="agent-actions">
        {agent.state === "in_call" && (
          <>
            <button
              type="button"
              className="ds-btn ds-btn-secondary ds-btn-sm"
              onClick={() => navigate("/supervisor/live-wall")}
            >
              监听
            </button>
            {isRiskL2 && (
              <button type="button" className="ds-btn ds-btn-sm" style={{ background: "#ef4444", color: "white" }}>
                强制转接
              </button>
            )}
          </>
        )}
        {agent.state === "just_ended" && (
          <button type="button" className="ds-btn ds-btn-secondary ds-btn-sm" onClick={() => navigate("/supervisor/reviews")}>
            查看摘要
          </button>
        )}
        {agent.state === "idle" && (
          <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={() => navigate("/supervisor/projects")}>
            分配任务
          </button>
        )}
      </div>
    </div>
  );
}

function PanelAlert({
  title, count, desc, onAction,
}: { title: string; count: number; desc: string; onAction: () => void }) {
  return (
    <div className="panel-alert">
      <div className="panel-alert-title">
        <AlertTriangle className="w-4 h-4" />
        {title} <strong>{count}条</strong>
      </div>
      <div style={{ fontSize: 13, color: "var(--color-neutral-700)", marginBottom: 12 }}>
        {desc}
      </div>
      <button
        type="button"
        className="ds-btn ds-btn-sm"
        style={{ background: "var(--color-warning)", color: "white" }}
        onClick={onAction}
      >
        立即复核 →
      </button>
    </div>
  );
}

function PanelRisk({ onView }: { onView: () => void }) {
  return (
    <div className="panel-risk">
      <div className="panel-risk-title">
        <AlertTriangle className="w-4 h-4" />
        今日风控告警
      </div>
      <div className="risk-event-item">
        <div>
          <span className="ds-badge ds-badge-red" style={{ fontSize: 11 }}>L2</span>
          <span style={{ marginLeft: 8, fontWeight: 500 }}>李小红</span>
          {" "}通话中检测到"
          <span style={{ color: "var(--color-danger)", fontWeight: 600 }}>不想交</span>
          "
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }}>
          <span style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>14:28</span>
          <button
            type="button"
            className="ds-btn ds-btn-secondary ds-btn-sm"
            onClick={onView}
            style={{ fontSize: 11.5, padding: "3px 8px" }}
          >
            查看
          </button>
        </div>
      </div>
    </div>
  );
}

function PanelStat({
  title, value, delta, label, barPct, footer, icon,
}: {
  title: string; value: string; delta: string; label: string;
  barPct: number; footer: string; icon: React.ReactNode;
}) {
  return (
    <div className="panel-stat">
      <div className="panel-stat-title">
        {icon}
        {title}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: "var(--color-neutral-900)" }}>{value}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-success)" }}>{delta}</span>
        <span style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>{label}</span>
      </div>
      <div style={{ background: "var(--color-neutral-200)", borderRadius: 6, height: 8, overflow: "hidden" }}>
        <div style={{ background: "var(--color-success)", height: "100%", width: `${barPct}%`, borderRadius: 6 }} />
      </div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-600)", marginTop: 8 }}>{footer}</div>
    </div>
  );
}

function PanelMinutes() {
  // 7 天柱状图（mock 数据）
  const weekly = [55, 62, 48, 70, 58, 80, 72];
  return (
    <div
      className="panel-stat"
      style={{ borderColor: "#fed7aa", background: "#fff7ed" }}
    >
      <div className="panel-stat-title" style={{ color: "#92400e" }}>
        <Clock className="w-4 h-4" />
        本组本月通话分钟
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: "#ea580c" }}>1,284</span>
        <span style={{ fontSize: 13, color: "#92400e" }}>分钟</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-success)" }}>↑8.2%</span>
      </div>
      <div style={{ background: "#fde68a", borderRadius: 4, height: 6, overflow: "hidden", marginBottom: 6 }}>
        <div style={{ background: "#d97706", height: "100%", width: "72%", borderRadius: 4 }} />
      </div>
      <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 36, marginBottom: 4 }}>
        {weekly.map((h, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              background: i === weekly.length - 1 ? "#ea580c" : "#fed7aa",
              borderRadius: "2px 2px 0 0",
              height: `${h}%`,
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#92400e" }}>
        <span>周一</span>
        <span>今天</span>
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-neutral-500)",
          marginTop: 8,
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        <BarChart2 className="w-3 h-3" />
        点击柱状图查看每日明细（v1.6 上线）
      </div>
    </div>
  );
}
