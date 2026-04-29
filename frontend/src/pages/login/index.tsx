import { useState } from "react";
import { useLogin } from "@refinedev/core";

export function LoginPage() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

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
        onError: (err) => {
          setErrorMsg(
            (err as { message?: string }).message ?? "登录失败，请重试",
          );
        },
      },
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-neutral-50)]">
      <div
        className="w-full bg-white rounded-lg p-8"
        style={{ maxWidth: 400, boxShadow: "var(--shadow-md)" }}
      >
        {/* Header */}
        <div className="mb-8">
          <h1
            className="font-bold text-[var(--color-primary)]"
            style={{ fontSize: 20 }}
          >
            有证慧催
          </h1>
          <p className="text-sm text-[var(--color-neutral-600)] mt-1">
            登录您的账号
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Phone */}
          <div>
            <label
              htmlFor="phone"
              className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1"
            >
              手机号
            </label>
            <input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="请输入手机号"
              required
              autoComplete="username"
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm text-[var(--color-neutral-900)] placeholder:text-[var(--color-neutral-400)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1"
            >
              密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
              autoComplete="current-password"
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm text-[var(--color-neutral-900)] placeholder:text-[var(--color-neutral-400)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {/* Error */}
          {errorMsg && (
            <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full text-white text-sm font-medium py-2 px-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "var(--color-primary-hover)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "var(--color-primary)";
            }}
          >
            {isLoading ? "登录中…" : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
