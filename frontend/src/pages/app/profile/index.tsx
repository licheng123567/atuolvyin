// v2.0 Task 3 — Screen 8：催收员个人信息（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-profile
// 数据源：
//   useGetIdentity()                  — name + role
//   GET /api/v1/agent/me/performance  — 三列 stats（本月通话/承诺数）
//   综合评分：固定 92（TODO 接 /agent/me/scoring-trend.avg_score_30d）
import { useState } from "react";
import { useCustom, useGetIdentity } from "@refinedev/core";
import { Bell, Info, Lock, Mic } from "lucide-react";
import type { AuthUser } from "../../../providers/auth-provider";
import { Bridge } from "../../../lib/jsBridge";

interface AgentPerformance {
  user_id: number;
  name: string;
  year_month: string;
  month_calls: number;
  month_connected: number;
  month_promised_cases: number;
  month_paid_cases: number;
  month_paid_amount: string;
  conversion_rate: number | null;
  minutes_used: number;
  minutes_quota: number | null;
  rank_in_tenant: number;
}

const ROLE_LABEL: Record<string, string> = {
  agent_internal: "内部催收员",
  agent_external: "外部催收员",
  supervisor: "督导",
  admin: "管理员",
};

const TOKEN_KEY = "autoluyin_token";
const USER_KEY = "autoluyin_user";

interface SettingsItemConfig {
  key: string;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  rightExtra?: React.ReactNode;
}

export function MobileProfilePage() {
  const { data: identity } = useGetIdentity<AuthUser>();
  const [toast, setToast] = useState<string | null>(null);

  const { query: perfQ } = useCustom<AgentPerformance>({
    url: "agent/me/performance",
    method: "get",
  });
  const perf = perfQ.data?.data;

  const name = identity?.name ?? "";
  const initial = name.slice(0, 1) || "用";
  const role = identity?.role ?? "";
  const roleLabel = ROLE_LABEL[role] ?? role ?? "用户";

  const monthCalls = perf?.month_calls ?? 0;
  const monthPromised = perf?.month_promised_cases ?? 0;
  // TODO: 接 GET /api/v1/agent/me/scoring-trend → avg_score_30d
  const compositeScore = 92;

  const showToast = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 1800);
  };

  const handleAbout = () => {
    const url = Bridge.getBackendUrl();
    showToast(`后端地址：${url || "未知"}`);
  };

  const handleLogout = () => {
    const ok = window.confirm("确定要退出登录吗？");
    if (!ok) return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    Bridge.notifyAuthError();
    window.location.href = "/login";
  };

  const settings: SettingsItemConfig[] = [
    {
      key: "notify",
      icon: <Bell size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "通知设置",
      onClick: () => showToast("TODO：通知设置"),
    },
    {
      key: "recording",
      icon: <Mic size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "录音模式",
      onClick: () => showToast("TODO：录音模式"),
    },
    {
      key: "password",
      icon: <Lock size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "修改密码",
      onClick: () => showToast("TODO：修改密码"),
    },
    {
      key: "about",
      icon: <Info size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "关于应用",
      onClick: handleAbout,
    },
  ];

  return (
    <div>
      {/* ── 头部蓝色渐变 ── */}
      <div className="profile-header">
        <div className="profile-avatar">{initial}</div>
        <div className="profile-name">{name || "未登录"}</div>
        <div className="profile-role">{roleLabel}</div>
      </div>

      {/* ── 三列 stats ── */}
      <div className="profile-stats">
        <div className="profile-stat">
          <div className="profile-stat-value">{monthCalls}</div>
          <div className="profile-stat-label">本月通话量</div>
        </div>
        <div className="profile-stat">
          <div className="profile-stat-value">{monthPromised}</div>
          <div className="profile-stat-label">本月承诺数</div>
        </div>
        <div className="profile-stat">
          <div className="profile-stat-value">{compositeScore}</div>
          <div className="profile-stat-label">综合评分</div>
        </div>
      </div>

      <div className="mobile-section-divider" />

      {/* ── 设置列表 ── */}
      <div className="settings-list">
        {settings.map((item) => (
          <button
            type="button"
            key={item.key}
            className="settings-item"
            onClick={item.onClick}
          >
            <span className="settings-item-icon">{item.icon}</span>
            <span className="settings-item-label">{item.label}</span>
            <span className="settings-item-arrow">›</span>
          </button>
        ))}
      </div>

      <div className="mobile-section-divider" />

      {/* ── 退出登录 ── */}
      <div className="logout-btn-wrap">
        <button type="button" className="logout-btn" onClick={handleLogout}>
          退出登录
        </button>
      </div>

      {/* 简易 toast */}
      {toast && (
        <div
          style={{
            position: "fixed",
            left: "50%",
            bottom: 80,
            transform: "translateX(-50%)",
            background: "rgba(17, 24, 39, 0.92)",
            color: "white",
            padding: "10px 16px",
            borderRadius: 8,
            fontSize: 13,
            maxWidth: "85%",
            textAlign: "center",
            zIndex: 1000,
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

export default MobileProfilePage;
