// v2.4 Module A — App 专属登录页（不复用 PC 双 panel 布局）
//
// 视觉规格（用户已选 sticky 底部表单方案）：
//   - 顶部 ~55% 渐变蓝背景：装饰圆 + 80×80 logo + 「有证慧催」品牌名 + slogan
//   - 下半 ~45% 白色圆角卡上推：tab + form + 提交
//   - 与 ui/app-agent.html 配色统一（#0f172a → #1e3a6e → #1A56DB 渐变）
//
// 仅给 App WebView 用（main-mobile.tsx 路由 /login → 这里）。
// PC main.tsx 仍用 frontend/src/pages/login/index.tsx（不动）。

import { useEffect, useState } from "react";
import { useLogin } from "@refinedev/core";
import { Eye, EyeOff, Phone, ShieldCheck, XCircle } from "lucide-react";
import type { LoginInput } from "../../../providers/auth-provider";

type LoginMode = "account-password" | "phone-otp";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

export function MobileLoginPage() {
  const [mode, setMode] = useState<LoginMode>("account-password");
  const [account, setAccount] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpHint, setOtpHint] = useState<string | null>(null);
  const [otpCountdown, setOtpCountdown] = useState(0);
  const [showPwd, setShowPwd] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

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
          : "验证码已发送，请查收短信",
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
    <div className="app-login">
      {/* 顶部渐变蓝 */}
      <div className="app-login-hero">
        <div className="app-login-deco-circle app-login-deco-1" />
        <div className="app-login-deco-circle app-login-deco-2" />
        <div className="app-login-brand">
          <div className="app-login-logo">
            <Phone size={36} strokeWidth={2} color="white" />
          </div>
          <div className="app-login-brand-name">
            有证<span className="app-login-brand-accent">慧催</span>
          </div>
          <div className="app-login-slogan">AI 辅助物业费催收系统</div>
        </div>
      </div>

      {/* 下半 sticky 卡 */}
      <div className="app-login-card">
        {/* 顶部抓手 */}
        <div className="app-login-handle" />

        {/* Login reason banner */}
        {loginReason && (
          <div className="app-login-banner-warn">
            <XCircle size={14} />
            <span>{loginReason}</span>
          </div>
        )}

        <h1 className="app-login-title">欢迎回来</h1>
        <p className="app-login-sub">请登录您的账号</p>

        {/* Tab */}
        <div className="app-login-tabs">
          {(
            [
              ["account-password", "账号密码"],
              ["phone-otp", "手机验证码"],
            ] as Array<[LoginMode, string]>
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`app-login-tab ${mode === key ? "active" : ""}`}
              onClick={() => {
                setMode(key);
                setErrorMsg("");
                setOtpHint(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Error banner */}
        {errorMsg && (
          <div className="app-login-banner-error">
            <XCircle size={14} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {mode === "account-password" ? (
            <div className="app-login-field">
              <label htmlFor="m-account">账号</label>
              <input
                id="m-account"
                type="text"
                value={account}
                onChange={(e) => setAccount(e.target.value)}
                placeholder="手机号 / 信用代码 / 邮箱"
                maxLength={120}
                autoComplete="username"
              />
            </div>
          ) : (
            <div className="app-login-field">
              <label htmlFor="m-phone">手机号</label>
              <input
                id="m-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="请输入 11 位手机号"
                maxLength={11}
                autoComplete="username"
              />
            </div>
          )}

          {mode === "phone-otp" ? (
            <div className="app-login-field">
              <label htmlFor="m-otp">短信验证码</label>
              <div className="app-login-otp-row">
                <input
                  id="m-otp"
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="6 位"
                  maxLength={8}
                  autoComplete="one-time-code"
                />
                <button
                  type="button"
                  className="app-login-otp-btn"
                  onClick={sendOtp}
                  disabled={otpCountdown > 0}
                >
                  {otpCountdown > 0 ? `${otpCountdown}s` : "获取验证码"}
                </button>
              </div>
              {otpHint && <p className="app-login-hint">{otpHint}</p>}
            </div>
          ) : (
            <div className="app-login-field">
              <label htmlFor="m-pwd">密码</label>
              <div className="app-login-pwd-wrap">
                <input
                  id="m-pwd"
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="app-login-pwd-toggle"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? "隐藏密码" : "显示密码"}
                >
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
          )}

          <button
            type="submit"
            className="app-login-submit"
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="app-login-spinner" />
            ) : (
              "登 录"
            )}
          </button>

          <div className="app-login-terms">
            <ShieldCheck size={11} />
            登录即表示您同意 <a href="#">服务条款</a> 和 <a href="#">隐私政策</a>
          </div>
        </form>
      </div>
    </div>
  );
}

export default MobileLoginPage;
