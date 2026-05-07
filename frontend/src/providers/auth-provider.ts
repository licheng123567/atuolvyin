import type { AuthProvider } from "@refinedev/core";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";
const TOKEN_KEY = "autoluyin_token";
const USER_KEY = "autoluyin_user";

export interface AuthUser {
  id: number;
  name: string;
  role: string;
  tenant_id: number | null;
  tenant_name: string | null;
  scope: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

interface LoginByAccount {
  mode?: "account-password";
  // 账号 = 手机号 / 18 位社会信用代码 / 邮箱（后端自动识别）
  account: string;
  password: string;
}

interface LoginByOtp {
  mode: "phone-otp";
  phone: string;
  code: string;
}

// v1.5 兼容字段保留：旧 phone-password / credit-code 入口已合并到 account-password
interface LoginByPhonePasswordLegacy {
  mode?: "phone-password";
  phone: string;
  password: string;
}

export type LoginInput =
  | LoginByAccount
  | LoginByOtp
  | LoginByPhonePasswordLegacy;

export const authProvider: AuthProvider = {
  login: async (input: LoginInput) => {
    try {
      let url: string;
      let body: Record<string, unknown>;
      if (input.mode === "phone-otp") {
        url = `${API_BASE}/api/v1/auth/otp/verify`;
        body = { phone: input.phone, code: input.code, device_type: "pc" };
      } else if ("account" in input) {
        // 统一账号入口：账号自动识别（手机号 / 信用代码 / 邮箱）
        url = `${API_BASE}/api/v1/auth/login-universal`;
        body = {
          account: input.account,
          password: input.password,
          device_type: "pc",
        };
      } else {
        // 兼容历史 phone-password 入口
        url = `${API_BASE}/api/v1/auth/login`;
        body = {
          phone: input.phone,
          password: input.password,
          device_type: "pc",
        };
      }

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          message?: string;
          detail?: { message?: string };
        };
        const msg = err.detail?.message ?? err.message ?? "登录失败，请检查输入";
        return {
          success: false,
          error: { name: "LoginError", message: msg },
        };
      }

      const data = (await res.json()) as {
        access_token: string;
        user_id: number;
        name: string;
        role: string;
        tenant_id: number | null;
        tenant_name: string | null;
        scope: string;
      };

      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(
        USER_KEY,
        JSON.stringify({
          id: data.user_id,
          name: data.name,
          role: data.role,
          tenant_id: data.tenant_id,
          tenant_name: data.tenant_name ?? null,
          scope: data.scope,
        } satisfies AuthUser),
      );

      return { success: true, redirectTo: "/" };
    } catch {
      return {
        success: false,
        error: { name: "NetworkError", message: "网络错误，请稍后重试" },
      };
    }
  },

  logout: async () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    return { success: true, redirectTo: "/login" };
  },

  check: async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      return { authenticated: false, redirectTo: "/login" };
    }
    return { authenticated: true };
  },

  onError: async (error: { status?: number; code?: string; message?: string }) => {
    if (error.status === 401 || error.status === 403) {
      // Sprint 15.1 — 多设备踢出：友好提示而非静默跳转
      if (error.code === "ERR_SESSION_EVICTED") {
        // 用 sessionStorage 暂存原因，登录页读出后展示 banner
        sessionStorage.setItem(
          "login_reason",
          "您的账号已在其他设备登录，请重新登录",
        );
      }
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      return { logout: true, redirectTo: "/login" };
    }
    return {};
  },

  getIdentity: async (): Promise<AuthUser | null> => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  },

  getPermissions: async (): Promise<string | null> => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return (JSON.parse(raw) as AuthUser).role;
  },
};
