// v2.0 Task 3 — WebView ↔ Native 桥接器（TS 端封装）
// 与 poc/android/.../JsBridge.kt 一一对应。
// 浏览器（非 Android WebView）调用时使用 fallback：navigate / console.warn。

declare global {
  interface Window {
    AndroidBridge?: {
      getJwt(): string;
      getBackendUrl(): string;
      getCapability(): string; // v2.1 — 返回 JSON string of CapabilityState
      dialCase(caseIdJson: string): void;
      scanQr(): void;
      openCaseDetail(caseId: number): void;
      notifyAuthError(): void;
    };
    __JWT__?: string;
  }
}

export interface DialPayload {
  case_id: number;
  phone: string;
  owner_name: string;
}

// v2.1 Task 6 — 设备录音能力等级
export type CapabilityLevel =
  | "realtime"
  | "post_upload"
  | "incompatible"
  | "unknown";

export interface CapabilityState {
  capability: CapabilityLevel;
  guidance: string;
  rom: string;
  /** epoch ms; 0 表示从未检测 */
  checkedAtMs: number;
}

const TOKEN_KEY = "autoluyin_token";

export const Bridge = {
  isAndroid: (): boolean =>
    typeof window !== "undefined" && !!window.AndroidBridge,

  getJwt: (): string => {
    if (typeof window === "undefined") return "";
    return (
      window.AndroidBridge?.getJwt() ??
      window.__JWT__ ??
      localStorage.getItem(TOKEN_KEY) ??
      ""
    );
  },

  getBackendUrl: (): string => {
    if (typeof window === "undefined") return "";
    const fallback =
      (import.meta.env.VITE_API_BASE as string | undefined) ??
      "http://localhost:18000";
    return window.AndroidBridge?.getBackendUrl() ?? fallback;
  },

  /**
   * v2.1 Task 6 — 同步获取设备录音能力。
   * - Android WebView：调 native getCapability() 返回 JSON string，TS 解析
   * - 浏览器 fallback：默认 realtime（开发顺畅，不被红 banner 干扰）
   */
  getCapability: (): CapabilityState => {
    if (typeof window === "undefined") {
      return {
        capability: "realtime",
        guidance: "开发模式",
        rom: "DEV",
        checkedAtMs: 0,
      };
    }
    const raw = window.AndroidBridge?.getCapability();
    if (!raw) {
      return {
        capability: "realtime",
        guidance: "浏览器调试模式",
        rom: "Browser",
        checkedAtMs: 0,
      };
    }
    try {
      const parsed = JSON.parse(raw) as CapabilityState;
      return parsed;
    } catch {
      return {
        capability: "unknown",
        guidance: "解析能力数据失败",
        rom: "",
        checkedAtMs: 0,
      };
    }
  },

  dialCase: (payload: DialPayload): void => {
    if (window.AndroidBridge?.dialCase) {
      window.AndroidBridge.dialCase(JSON.stringify(payload));
    } else {
      // eslint-disable-next-line no-console
      console.warn("[browser] would dial", payload);
    }
  },

  scanQr: (): void => {
    if (window.AndroidBridge?.scanQr) {
      window.AndroidBridge.scanQr();
    } else {
      // eslint-disable-next-line no-console
      console.warn("[browser] would scan QR");
    }
  },

  openCaseDetail: (id: number): void => {
    window.AndroidBridge?.openCaseDetail(id);
  },

  notifyAuthError: (): void => {
    window.AndroidBridge?.notifyAuthError();
  },
};

export {};
