import type { AuthProvider } from "@refinedev/core";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";
const TOKEN_KEY = "autoluyin_token";
const USER_KEY = "autoluyin_user";

export interface AuthUser {
  id: number;
  name: string;
  role: string;
  tenant_id: number | null;
  scope: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export const authProvider: AuthProvider = {
  login: async ({ phone, password }: { phone: string; password: string }) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Sprint 15.1 — 多设备踢出：PC 端固定 device_type='pc'
        body: JSON.stringify({ phone, password, device_type: "pc" }),
      });

      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          message?: string;
        };
        return {
          success: false,
          error: {
            name: "LoginError",
            message: err.message ?? "登录失败，请检查手机号和密码",
          },
        };
      }

      const data = (await res.json()) as {
        access_token: string;
        user_id: number;
        name: string;
        role: string;
        tenant_id: number | null;
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
