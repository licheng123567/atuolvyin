// 1:1 还原 ui/login.html — 双面板 + 记住设备 + 忘记密码
// 登录入口不区分平台/对外（v1.6 决策）：所有角色统一同一入口；如需区分平台后台，
// 走独立 URL（例：/platform-login）即可，无需在 UI 上切换。
//
// v1.4 S17.4 — 新增 信用代码 / 短信验证码 两种登录模式（mode 切换）。
import { Eye, EyeOff, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useLogin } from "@refinedev/core";
import type { LoginInput } from "../../providers/auth-provider";

type LoginMode = "account-password" | "phone-otp";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

interface FeatureItem {
  emoji: string;
  title: string;
  desc: string;
}

const FEATURES: FeatureItem[] = [
  {
    emoji: "🎙️",
    title: "实时 AI 话术辅助",
    desc: "通话中即时识别业主异议，推送应对话术，延迟 ≤ 3 秒",
  },
  {
    emoji: "📊",
    title: "智能 CRM 管理",
    desc: "公海/私海自动流转，优先级评分，联系频次合规管控",
  },
  {
    emoji: "⚖️",
    title: "合规留证",
    desc: "通话录音区块链存证，催收行为合规月报，法务无缝转接",
  },
  {
    emoji: "📱",
    title: "App-PC 联动",
    desc: "手机拨打 + PC 实时监控，督导远程辅助，团队效率最大化",
  },
];

export function LoginPage() {
  const [mode, setMode] = useState<LoginMode>("account-password");
  // 「账号密码」标签下的 account 接受手机号 / 18 位社会信用代码 / 邮箱
  const [account, setAccount] = useState("");
  // 「手机验证码」标签下用 phone
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpHint, setOtpHint] = useState<string | null>(null);
  const [otpCountdown, setOtpCountdown] = useState(0);
  const [showPwd, setShowPwd] = useState(false);
  const [remember, setRemember] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [showForgot, setShowForgot] = useState(false);

  useEffect(() => {
    if (otpCountdown <= 0) return;
    const t = setTimeout(() => setOtpCountdown((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [otpCountdown]);

  const [loginReason] = useState<string | null>(() => {
    if (typeof sessionStorage === "undefined") return null;
    const r = sessionStorage.getItem("login_reason");
    if (r) sessionStorage.removeItem("login_reason");
    return r;
  });

  const { mutate: login, isPending: isLoading } = useLogin<LoginInput>();

  const sendOtp = async () => {
    setErrorMsg("");
    setOtpHint(null);
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      setErrorMsg("请填写有效的 11 位手机号");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/otp/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, purpose: "login" }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        sent?: boolean;
        dev_code?: string;
        detail?: { message?: string };
      };
      if (!res.ok || !data.sent) {
        setErrorMsg(data.detail?.message ?? "发送验证码失败，请稍后再试");
        return;
      }
      setOtpCountdown(60);
      setOtpHint(
        data.dev_code
          ? `开发模式：验证码 ${data.dev_code}（5 分钟内有效）`
          : "验证码已发送，请查收短信（5 分钟内有效）",
      );
    } catch {
      setErrorMsg("网络错误，请稍后重试");
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg("");
    let payload: LoginInput;
    if (mode === "phone-otp") {
      if (!phone || !otpCode) {
        setErrorMsg("请填写手机号和验证码");
        return;
      }
      payload = { mode: "phone-otp", phone, code: otpCode };
    } else {
      if (!account || !password) {
        setErrorMsg("请填写账号和密码");
        return;
      }
      payload = { mode: "account-password", account: account.trim(), password };
    }
    login(payload, {
      onSuccess: (data) => {
        const result = data as { success?: boolean; error?: { message?: string } };
        if (result.success === false) {
          setErrorMsg(result.error?.message ?? "登录失败，请重试");
        }
      },
      onError: (err) => {
        setErrorMsg((err as { message?: string }).message ?? "登录失败，请重试");
      },
    });
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#f0f4f8" }}>
      {/* ── Left Panel ─────────────────────────────────────── */}
      <div
        className="hidden md:flex"
        style={{
          width: 480,
          flexShrink: 0,
          background:
            "linear-gradient(160deg,#0f172a 0%,#1e3a6e 50%,#1A56DB 100%)",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "48px 48px 40px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Decorative circles */}
        <div
          style={{
            content: "''",
            position: "absolute",
            top: -60,
            right: -60,
            width: 320,
            height: 320,
            borderRadius: "50%",
            background: "rgba(255,255,255,.04)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: -80,
            left: -40,
            width: 280,
            height: 280,
            borderRadius: "50%",
            background: "rgba(255,255,255,.03)",
          }}
        />

        {/* Brand */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <div
            style={{
              fontSize: 28,
              fontWeight: 800,
              color: "white",
              letterSpacing: "-0.5px",
              marginBottom: 8,
            }}
          >
            有证
            <span
              style={{
                background: "linear-gradient(90deg,#60a5fa,#a78bfa)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              慧催
            </span>
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.6)" }}>
            AI 辅助物业费催收系统
          </div>
        </div>

        {/* Features */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          {FEATURES.map((f) => (
            <div
              key={f.title}
              style={{ display: "flex", alignItems: "flex-start", gap: 14 }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: "rgba(255,255,255,.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  fontSize: 18,
                }}
              >
                {f.emoji}
              </div>
              <div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "white",
                    marginBottom: 2,
                  }}
                >
                  {f.title}
                </div>
                <div style={{ fontSize: 12.5, color: "rgba(255,255,255,.5)" }}>
                  {f.desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            position: "relative",
            zIndex: 1,
            fontSize: 12,
            color: "rgba(255,255,255,.3)",
          }}
        >
          © 2026 有证慧催 · v1.6
        </div>
      </div>

      {/* ── Right Panel ────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 20px",
        }}
      >
        <div style={{ width: "100%", maxWidth: 440 }}>
          <h1
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: "#111827",
              marginBottom: 6,
            }}
          >
            {showForgot ? "重置密码" : "欢迎回来"}
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "#6b7280",
              marginBottom: showForgot ? 20 : 32,
            }}
          >
            {showForgot ? "输入您注册的手机号，系统将发送验证码" : "请登录您的账号"}
          </p>

          {/* Login reason banner (Sprint 15.1 多设备踢出) */}
          {loginReason && !showForgot && (
            <div
              style={{
                color: "#92400e",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: 8,
                padding: "12px 16px",
                fontSize: 13.5,
                marginBottom: 18,
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
              }}
            >
              <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{loginReason}</span>
            </div>
          )}

          {/* ──── 主登录表单 ──── */}
          {!showForgot && (
            <form onSubmit={handleSubmit}>
              {/* v1.4 — 登录方式：账号密码（手机/信用代码/邮箱）/ 手机验证码 */}
              <div
                style={{
                  display: "flex",
                  gap: 0,
                  marginBottom: 18,
                  borderBottom: "1px solid #e5e7eb",
                }}
              >
                {([
                  ["account-password", "账号密码"],
                  ["phone-otp", "手机验证码"],
                ] as Array<[LoginMode, string]>).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setMode(key);
                      setErrorMsg("");
                      setOtpHint(null);
                    }}
                    style={{
                      padding: "10px 14px",
                      fontSize: 13,
                      fontWeight: mode === key ? 600 : 400,
                      color: mode === key ? "#1A56DB" : "#6b7280",
                      borderBottom:
                        mode === key ? "2px solid #1A56DB" : "2px solid transparent",
                      background: "none",
                      border: "none",
                      borderBottomWidth: 2,
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Error */}
              {errorMsg && (
                <div
                  style={{
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 8,
                    padding: "12px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 18,
                    fontSize: 13.5,
                    color: "#991b1b",
                  }}
                >
                  <XCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {mode === "account-password" ? (
                <div style={{ marginBottom: 18 }}>
                  <label
                    htmlFor="account"
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: 6,
                    }}
                  >
                    账号
                    <span style={{ color: "#e02424", marginLeft: 2 }}>*</span>
                  </label>
                  <input
                    id="account"
                    type="text"
                    value={account}
                    onChange={(e) => setAccount(e.target.value)}
                    placeholder="手机号 / 18 位社会信用代码 / 邮箱"
                    maxLength={120}
                    autoComplete="username"
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      border: errorMsg ? "1px solid #e02424" : "1px solid #d1d5db",
                      borderRadius: 8,
                      fontSize: 14,
                      fontFamily: "inherit",
                      color: "#111827",
                      background: "white",
                      outline: "none",
                      transition: "border-color .15s",
                    }}
                  />
                </div>
              ) : (
                <div style={{ marginBottom: 18 }}>
                  <label
                    htmlFor="phone"
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: 6,
                    }}
                  >
                    手机号
                    <span style={{ color: "#e02424", marginLeft: 2 }}>*</span>
                  </label>
                  <input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="请输入 11 位手机号"
                    maxLength={11}
                    autoComplete="username"
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      border: errorMsg ? "1px solid #e02424" : "1px solid #d1d5db",
                      borderRadius: 8,
                      fontSize: 14,
                      fontFamily: "inherit",
                      color: "#111827",
                      background: "white",
                      outline: "none",
                      transition: "border-color .15s",
                    }}
                  />
                </div>
              )}

              {mode === "phone-otp" ? (
                <div style={{ marginBottom: 18 }}>
                  <label
                    htmlFor="otp"
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: 6,
                    }}
                  >
                    短信验证码<span style={{ color: "#e02424", marginLeft: 2 }}>*</span>
                  </label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="otp"
                      type="text"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                      placeholder="6 位验证码"
                      maxLength={8}
                      autoComplete="one-time-code"
                      style={{
                        flex: 1,
                        padding: "10px 14px",
                        border: errorMsg ? "1px solid #e02424" : "1px solid #d1d5db",
                        borderRadius: 8,
                        fontSize: 14,
                        fontFamily: "monospace",
                        letterSpacing: 4,
                        textAlign: "center",
                        color: "#111827",
                        background: "white",
                        outline: "none",
                      }}
                    />
                    <button
                      type="button"
                      onClick={sendOtp}
                      disabled={otpCountdown > 0}
                      style={{
                        padding: "0 14px",
                        background: otpCountdown > 0 ? "#e5e7eb" : "#1A56DB",
                        color: otpCountdown > 0 ? "#6b7280" : "white",
                        border: "none",
                        borderRadius: 8,
                        fontSize: 13,
                        fontWeight: 500,
                        cursor: otpCountdown > 0 ? "not-allowed" : "pointer",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {otpCountdown > 0 ? `${otpCountdown}s 后重发` : "获取验证码"}
                    </button>
                  </div>
                  {otpHint && (
                    <p
                      style={{
                        marginTop: 6,
                        fontSize: 12,
                        color: "#6b7280",
                      }}
                    >
                      {otpHint}
                    </p>
                  )}
                </div>
              ) : (
                <div style={{ marginBottom: 18 }}>
                  <label
                    htmlFor="password"
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: 6,
                    }}
                  >
                    密码<span style={{ color: "#e02424", marginLeft: 2 }}>*</span>
                  </label>
                  <div style={{ position: "relative" }}>
                    <input
                      id="password"
                      type={showPwd ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="请输入密码"
                      autoComplete="current-password"
                      style={{
                        width: "100%",
                        padding: "10px 44px 10px 14px",
                        border: errorMsg ? "1px solid #e02424" : "1px solid #d1d5db",
                        borderRadius: 8,
                        fontSize: 14,
                        fontFamily: "inherit",
                        color: "#111827",
                        background: "white",
                        outline: "none",
                        transition: "border-color .15s",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd((v) => !v)}
                      aria-label={showPwd ? "隐藏密码" : "显示密码"}
                      style={{
                        position: "absolute",
                        right: 12,
                        top: "50%",
                        transform: "translateY(-50%)",
                        cursor: "pointer",
                        color: "#9ca3af",
                        border: "none",
                        background: "none",
                        padding: 2,
                      }}
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Remember + Forgot */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 24,
                }}
              >
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    cursor: "pointer",
                    fontSize: 13,
                    color: "#374151",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                  />
                  <span>记住此设备（7 天内免登录）</span>
                </label>
                <span
                  onClick={() => setShowForgot(true)}
                  style={{
                    fontSize: 13,
                    color: "#1A56DB",
                    cursor: "pointer",
                  }}
                >
                  忘记密码？
                </span>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading}
                style={{
                  width: "100%",
                  padding: 12,
                  background: "#1A56DB",
                  color: "white",
                  border: "none",
                  borderRadius: 8,
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: isLoading ? "not-allowed" : "pointer",
                  opacity: isLoading ? 0.6 : 1,
                  transition: "background .15s",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                }}
              >
                {isLoading ? (
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      border: "2px solid rgba(255,255,255,.3)",
                      borderTopColor: "white",
                      borderRadius: "50%",
                      animation: "spin 0.7s linear infinite",
                    }}
                  />
                ) : (
                  "登 录"
                )}
              </button>

              {/* Terms */}
              <div
                style={{
                  marginTop: 16,
                  textAlign: "center",
                  fontSize: 12.5,
                  color: "#9ca3af",
                }}
              >
                登录即表示您同意
                <a href="#" style={{ color: "#1A56DB", marginLeft: 4 }}>
                  服务条款
                </a>
                {" 和 "}
                <a href="#" style={{ color: "#1A56DB" }}>
                  隐私政策
                </a>
              </div>
            </form>
          )}

          {/* ──── 忘记密码表单 ──── */}
          {showForgot && (
            <ForgotPasswordForm onBack={() => setShowForgot(false)} />
          )}

          {/* Spinner keyframes */}
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    </div>
  );
}

function ForgotPasswordForm({ onBack }: { onBack: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [secs, setSecs] = useState(0);

  const sendCode = () => {
    if (!phone) return;
    setSecs(60);
    const t = setInterval(() => {
      setSecs((s) => {
        if (s <= 1) {
          clearInterval(t);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  };

  return (
    <div>
      <div
        style={{
          background: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: 20,
          padding: "4px 12px",
          fontSize: 12,
          color: "#065f46",
          marginBottom: 20,
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <ShieldCheck className="w-3.5 h-3.5" />
        重置流程受系统保护，全程加密
      </div>
      <div style={{ marginBottom: 18 }}>
        <label
          style={{
            display: "block",
            fontSize: 13,
            fontWeight: 500,
            color: "#374151",
            marginBottom: 6,
          }}
        >
          手机号<span style={{ color: "#e02424", marginLeft: 2 }}>*</span>
        </label>
        <input
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="请输入注册手机号"
          maxLength={11}
          style={{
            width: "100%",
            padding: "10px 14px",
            border: "1px solid #d1d5db",
            borderRadius: 8,
            fontSize: 14,
            color: "#111827",
            background: "white",
            outline: "none",
          }}
        />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="验证码"
          maxLength={6}
          style={{
            flex: 1,
            padding: "10px 14px",
            border: "1px solid #d1d5db",
            borderRadius: 8,
            fontSize: 14,
            color: "#111827",
            background: "white",
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={sendCode}
          disabled={!phone || secs > 0}
          style={{
            padding: "10px 16px",
            background: "white",
            border: "1px solid #d1d5db",
            borderRadius: 8,
            fontSize: 13,
            cursor: phone && secs === 0 ? "pointer" : "not-allowed",
            whiteSpace: "nowrap",
            color: "#374151",
            opacity: phone && secs === 0 ? 1 : 0.5,
          }}
        >
          {secs > 0 ? `${secs}s 后重发` : "获取验证码"}
        </button>
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: "#9ca3af" }}>
        验证码 10 分钟内有效 · 来自"有证慧催"
      </div>
      <button
        type="button"
        style={{
          marginTop: 20,
          width: "100%",
          padding: 12,
          background: "#1A56DB",
          color: "white",
          border: "none",
          borderRadius: 8,
          fontSize: 15,
          fontWeight: 600,
          cursor: "pointer",
        }}
        onClick={() => alert("重置链接已发送至您的手机")}
      >
        发送重置链接
      </button>
      <div style={{ marginTop: 14, textAlign: "center" }}>
        <span
          onClick={onBack}
          style={{ color: "#6b7280", fontSize: 13, cursor: "pointer" }}
        >
          ← 返回登录
        </span>
      </div>
    </div>
  );
}
