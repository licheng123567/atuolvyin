// v2.0 Task 3 — Screen 8：催收员个人信息（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-profile
// 数据源：
//   useGetIdentity()                  — name + role
//   GET /api/v1/agent/me/performance  — 三列 stats（本月通话/承诺数）
//   综合评分：固定 92（TODO 接 /agent/me/scoring-trend.avg_score_30d）
import { useState } from "react";
import { useCustom, useGetIdentity } from "@refinedev/core";
import { Bell, Info, Lock } from "lucide-react";
import type { AuthUser } from "../../../providers/auth-provider";
import { Bridge, type CapabilityState } from "../../../lib/jsBridge";

/**
 * v2.3.1 — 录音设置内联 section（替代 v2.3 的 BottomSheet）。
 * 一屏展示：当前模式、3 模式对比、上传目录 + 修改入口。用户反馈：弹窗看不清。
 */
// v0.5.2 — 修正：实时录音其实是「老 Android（6–9）」可用；Android 10+ 系统加强了
// 录音权限管控，App 拿不到通话流，只能挂断后扫描文件 → 事后上传。
const MODES = [
  {
    key: "realtime",
    label: "实时录音",
    emoji: "🟢",
    accent: "#10b981",
    tagline: "通话中 AI 实时辅助话术（Android 6–9 早期 ROM 可用）",
  },
  {
    key: "post_upload",
    label: "通话后上传",
    emoji: "🟡",
    accent: "#f59e0b",
    tagline: "挂断后扫描录音文件并上传（Android 10+ 系统限制录音流）",
  },
  {
    key: "incompatible",
    label: "不支持录音",
    emoji: "🔴",
    accent: "#ef4444",
    tagline: "ROM 完全不允许 App 访问通话录音，无 AI 分析",
  },
] as const;

function formatDirUri(raw: string): string {
  if (!raw) return "";
  try {
    const m = raw.match(/tree\/([^/]+)(?:\/(.+))?$/);
    if (m) {
      const path = decodeURIComponent(m[2] ?? m[1]);
      return "/" + path.replace(/^primary:/, "").replace(/^[^:]+:/, "");
    }
  } catch {
    /* ignore */
  }
  return raw.length > 40 ? "…" + raw.slice(-37) : raw;
}

function RecordingSection() {
  const state: CapabilityState = Bridge.getCapability();
  const currentDirUri = Bridge.getRecordingDirUri();
  const dirFriendly = formatDirUri(currentDirUri);

  return (
    <div className="profile-section-card">
      <div className="profile-section-title">录音设置</div>
      <p className="recording-section-sub">
        模式由设备型号 + Android 版本自动决定，不可手动切换。
      </p>

      {/* 3 模式对比卡 */}
      <div className="recording-modes">
        {MODES.map((m) => {
          const active = m.key === state.capability;
          return (
            <div
              key={m.key}
              className={`recording-mode-row ${active ? "active" : ""}`}
              style={
                active
                  ? {
                      borderColor: m.accent,
                      background: `${m.accent}0d`,
                    }
                  : undefined
              }
            >
              <span className="recording-mode-emoji">{m.emoji}</span>
              <div className="recording-mode-text">
                <div className="recording-mode-label">
                  {m.label}
                  {active && (
                    <span
                      className="recording-mode-current"
                      style={{ color: m.accent, borderColor: m.accent }}
                    >
                      ✓ 当前
                    </span>
                  )}
                </div>
                <div className="recording-mode-tagline">{m.tagline}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 设备 ROM hint + 上次检测 */}
      {state.rom && (
        <p className="recording-rom">
          当前设备：{state.rom}
          {state.checkedAtMs > 0 && (
            <span className="recording-checked-at">
              {" · "}
              检测于 {new Date(state.checkedAtMs).toLocaleString("zh-CN")}
            </span>
          )}
        </p>
      )}

      {/* v0.5.2 — 录音文件夹：当前设置 + 系统推荐目录 + 修改按钮 */}
      <div className="recording-dir-row">
        <div className="recording-dir-info">
          <div className="recording-dir-label">录音文件夹</div>
          <div className="recording-dir-value" title={currentDirUri || ""}>
            {dirFriendly || "未设置（使用系统默认扫描）"}
          </div>
          <div className="recording-dir-hint">
            {(() => {
              const suggested = Bridge.getSuggestedRecordingDir();
              return suggested
                ? `本机推荐：/${suggested}（修改时会自动跳到此目录附近）`
                : "提示：通常文件夹名含 \"call\" 或 \"录音\"";
            })()}
          </div>
        </div>
        <button
          type="button"
          className="recording-dir-change-btn"
          onClick={() => Bridge.openRecordingDirPicker()}
        >
          修改
        </button>
      </div>
    </div>
  );
}

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
  // agent role covers both internal and external (work_mode distinguishes them)
  agent: "催收员",
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
  // v0.5.2 — App 内修改密码（不跳 PC）
  const [pwdFormOpen, setPwdFormOpen] = useState(false);
  const [pwdOld, setPwdOld] = useState("");
  const [pwdNew, setPwdNew] = useState("");
  const [pwdConfirm, setPwdConfirm] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSubmitting, setPwdSubmitting] = useState(false);

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

  const submitChangePassword = async () => {
    setPwdError(null);
    if (pwdNew.length < 8) {
      setPwdError("新密码至少 8 位");
      return;
    }
    if (pwdNew !== pwdConfirm) {
      setPwdError("两次新密码不一致");
      return;
    }
    setPwdSubmitting(true);
    try {
      const backend = Bridge.getBackendUrl();
      const token = Bridge.getJwt();
      const res = await fetch(`${backend}/api/v1/me/password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: pwdOld || null,
          new_password: pwdNew,
        }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          detail?: { message?: string };
          message?: string;
        };
        const msg =
          err.detail?.message ??
          err.message ??
          (res.status === 403 ? "当前密码错误" : "修改失败，请重试");
        setPwdError(msg);
        return;
      }
      // 成功：关表单、清字段、提示
      setPwdFormOpen(false);
      setPwdOld("");
      setPwdNew("");
      setPwdConfirm("");
      showToast("密码已更新");
    } catch {
      setPwdError("网络异常，请重试");
    } finally {
      setPwdSubmitting(false);
    }
  };

  const handleLogout = () => {
    const ok = window.confirm("确定要退出登录吗？");
    if (!ok) return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    Bridge.notifyAuthError();
    window.location.href = "/login";
  };

  // v2.3.1 — 录音模式/上传目录从这里挪到独立 RecordingSection 内联展示
  const settings: SettingsItemConfig[] = [
    {
      key: "notify",
      icon: <Bell size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "通知设置",
      onClick: () => showToast("TODO：通知设置（待 MiPush 接入）"),
    },
    {
      key: "password",
      icon: <Lock size={16} strokeWidth={1.5} color="#9CA3AF" />,
      label: "修改密码",
      onClick: () => {
        setPwdError(null);
        setPwdFormOpen((v) => !v);
      },
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
            {item.rightExtra}
            <span className="settings-item-arrow">›</span>
          </button>
        ))}
      </div>

      {/* v0.5.2 — 修改密码内联表单（点击「修改密码」展开） */}
      {pwdFormOpen && (
        <div className="profile-section-card password-form">
          <div className="profile-section-title">修改密码</div>
          <input
            type="password"
            placeholder="当前密码（未设置可留空）"
            value={pwdOld}
            onChange={(e) => setPwdOld(e.target.value)}
            autoComplete="current-password"
            className="password-input"
          />
          <input
            type="password"
            placeholder="新密码（≥ 8 位）"
            value={pwdNew}
            onChange={(e) => setPwdNew(e.target.value)}
            autoComplete="new-password"
            className="password-input"
          />
          <input
            type="password"
            placeholder="再次输入新密码"
            value={pwdConfirm}
            onChange={(e) => setPwdConfirm(e.target.value)}
            autoComplete="new-password"
            className="password-input"
          />
          {pwdError && <div className="password-error">{pwdError}</div>}
          <div className="password-actions">
            <button
              type="button"
              className="password-cancel"
              onClick={() => {
                setPwdFormOpen(false);
                setPwdError(null);
              }}
            >
              取消
            </button>
            <button
              type="button"
              className="password-submit"
              onClick={submitChangePassword}
              disabled={pwdSubmitting}
            >
              {pwdSubmitting ? "提交中…" : "确认修改"}
            </button>
          </div>
        </div>
      )}

      <div className="mobile-section-divider" />

      {/* ── v2.3.1 — 录音设置内联 section（模式说明 + 上传目录 + 修改入口） ── */}
      <RecordingSection />

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
