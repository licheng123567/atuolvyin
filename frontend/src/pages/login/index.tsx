// Sprint 16.5 (UI 还原) — 登录页对齐 ui/login.html 双面板设计
import { Eye, EyeOff, Headphones, Scale, Smartphone, TrendingUp, XCircle } from "lucide-react";
import { useState } from "react";
import { useLogin } from "@refinedev/core";

interface FeatureItem {
  icon: React.ReactNode;
  title: string;
  desc: string;
}

const FEATURES: FeatureItem[] = [
  {
    icon: <Headphones className="w-5 h-5" />,
    title: "实时 AI 话术辅助",
    desc: "通话中即时识别业主异议，推送应对话术，延迟 ≤ 3 秒",
  },
  {
    icon: <TrendingUp className="w-5 h-5" />,
    title: "智能 CRM 管理",
    desc: "公海/私海自动流转，优先级评分，联系频次合规管控",
  },
  {
    icon: <Scale className="w-5 h-5" />,
    title: "合规留证",
    desc: "通话录音区块链存证，催收行为合规月报，法务无缝转接",
  },
  {
    icon: <Smartphone className="w-5 h-5" />,
    title: "App-PC 联动",
    desc: "手机拨打 + PC 实时监控，督导远程辅助，团队效率最大化",
  },
];

export function LoginPage() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  // Sprint 15.1 — 多设备踢出场景下展示原因横幅；lazy initializer 避免 setState-in-effect
  const [loginReason] = useState<string | null>(() => {
    if (typeof sessionStorage === "undefined") return null;
    const r = sessionStorage.getItem("login_reason");
    if (r) sessionStorage.removeItem("login_reason");
    return r;
  });

  const { mutate: login, isPending: isLoading } = useLogin<{
    phone: string;
    password: string;
  }>();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg("");
    login(
      { phone, password },
      {
        // Refine v5：auth-provider 返回 { success:false, error } 时
        // 走 onSuccess（带 data）而非 onError；onError 只在 promise 真 reject 时触发
        onSuccess: (data) => {
          const result = data as { success?: boolean; error?: { message?: string } };
          if (result.success === false) {
            setErrorMsg(result.error?.message ?? "登录失败，请重试");
          }
        },
        onError: (err) => {
          setErrorMsg(
            (err as { message?: string }).message ?? "登录失败，请重试",
          );
        },
      },
    );
  };

  return (
    <div className="min-h-screen flex" style={{ background: "#f0f4f8" }}>
      {/* Left brand panel */}
      <div
        className="hidden md:flex flex-col justify-between flex-shrink-0 relative overflow-hidden"
        style={{
          width: 480,
          padding: "48px 48px 40px",
          background:
            "linear-gradient(160deg, #0f172a 0%, #1e3a6e 50%, #1A56DB 100%)",
        }}
      >
        {/* Decorative circles */}
        <div
          className="absolute pointer-events-none"
          style={{
            top: -60,
            right: -60,
            width: 320,
            height: 320,
            borderRadius: "50%",
            background: "rgba(255,255,255,.04)",
          }}
        />
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: -80,
            left: -40,
            width: 280,
            height: 280,
            borderRadius: "50%",
            background: "rgba(255,255,255,.03)",
          }}
        />

        {/* Brand */}
        <div className="relative z-10">
          <div
            className="font-extrabold mb-2"
            style={{
              fontSize: 28,
              color: "white",
              letterSpacing: "-0.5px",
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
          <div
            style={{ fontSize: 13, color: "rgba(255,255,255,.6)" }}
          >
            AI 辅助物业费催收系统
          </div>
        </div>

        {/* Features */}
        <div className="relative z-10 flex flex-col gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="flex items-start gap-3.5">
              <div
                className="flex-shrink-0 flex items-center justify-center"
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: "rgba(255,255,255,.1)",
                  color: "white",
                }}
              >
                {f.icon}
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
                <div
                  style={{ fontSize: 12.5, color: "rgba(255,255,255,.5)" }}
                >
                  {f.desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          className="relative z-10"
          style={{ fontSize: 12, color: "rgba(255,255,255,.3)" }}
        >
          © 2026 有证慧催 · v1.5
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center" style={{ padding: "40px 20px" }}>
        <div className="w-full" style={{ maxWidth: 440 }}>
          <h1
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: "#111827",
              marginBottom: 6,
            }}
          >
            欢迎回来
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "#6b7280",
              marginBottom: 32,
            }}
          >
            请登录您的账号
          </p>

          {loginReason && (
            <div
              className="flex items-start gap-2 mb-4 px-3 py-2 text-sm"
              style={{
                color: "#92400e",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "var(--radius-md)",
              }}
            >
              <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{loginReason}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Phone */}
            <div>
              <label
                htmlFor="phone"
                className="block mb-1.5"
                style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}
              >
                手机号 / 账号<span className="text-red-500 ml-0.5">*</span>
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="请输入手机号"
                required
                autoComplete="username"
                maxLength={11}
                className="w-full px-3.5 py-2.5 text-sm outline-none transition-colors"
                style={{
                  border: "1px solid #d1d5db",
                  borderRadius: 8,
                  color: "#111827",
                }}
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block mb-1.5"
                style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}
              >
                密码<span className="text-red-500 ml-0.5">*</span>
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  required
                  autoComplete="current-password"
                  className="w-full px-3.5 py-2.5 pr-10 text-sm outline-none transition-colors"
                  style={{
                    border: "1px solid #d1d5db",
                    borderRadius: 8,
                    color: "#111827",
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? "隐藏密码" : "显示密码"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600"
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {errorMsg && (
              <div
                className="flex items-start gap-2 px-3 py-2 text-sm"
                style={{
                  color: "#b91c1c",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: 6,
                }}
              >
                <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full text-white text-sm font-semibold py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: "var(--color-primary)",
                borderRadius: 8,
                marginTop: 8,
              }}
            >
              {isLoading ? "登录中…" : "登 录"}
            </button>
          </form>

          <div
            className="mt-4 text-center"
            style={{ fontSize: 12.5, color: "#9ca3af" }}
          >
            登录即表示您同意
            <a href="#" style={{ color: "var(--color-primary)", marginLeft: 4 }}>
              服务条款
            </a>{" "}
            和{" "}
            <a href="#" style={{ color: "var(--color-primary)" }}>
              隐私政策
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
