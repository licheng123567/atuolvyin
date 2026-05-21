import type { AuthProvider } from "@refinedev/core";
import { Bridge } from "../lib/jsBridge";

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
  // v0.7.0 — 服务商催收员标识(work_mode='external')便于前端按需展示差异化 UI;
  // 物业催收员 work_mode='internal';非 agent 角色为 null。
  // 后端 /auth/me 已返回(若没有,前端 default null,UI 走通用路径)。
  work_mode?: "internal" | "external" | null;
  provider_id?: number | null;
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
          code?: string;
          message?: string;
          detail?: { code?: string; message?: string };
        };
        // v2.3 — 中文化错误。优先用后端 detail.message / message（已含中文）。
        // 否则按 HTTP status 给人类化文案；最后才用 fallback。
        const backendMsg = err.detail?.message ?? err.message;
        const statusFallback: Record<number, string> = {
          401: "账号或密码错误，请重试",
          403: "无权限登录",
          404: "账号不存在",
          422: "输入格式不正确，请检查后重试",
          429: "请求过于频繁，请稍后再试",
          500: "服务器暂时不可用，请稍后重试",
          502: "服务器暂时不可用，请稍后重试",
          503: "服务器暂时不可用，请稍后重试",
        };
        const msg = backendMsg ?? statusFallback[res.status] ?? "登录失败，请重试";
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
      // v0.5.2 — App WebView 路径：把 JWT 推回 native（CallWatcherService /
      // ApiClient 都依赖 AppConfig.jwtToken）。浏览器 no-op。
      Bridge.saveJwt(data.access_token);

      return { success: true, redirectTo: "/" };
    } catch {
      // v2.3 — 网络层错误（fetch 失败：DNS / 服务不可达 / CORS 等）
      return {
        success: false,
        error: {
          name: "NetworkError",
          message: "网络异常，请检查 WiFi/移动数据后重试",
        },
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
    // v1.5.7 — 只在 401（认证失败 / 会话失效）时强制登出
    // 403（认证有效但当前角色无权限）应保持登录，让页面自行处理（如显示「无权限」），
    // 否则多角色用户访问到非自己角色的端点会被误踢回登录页。
    if (error.status === 401) {
      if (error.code === "ERR_SESSION_EVICTED") {
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
