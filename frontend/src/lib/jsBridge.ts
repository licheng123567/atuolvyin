// v2.0 Task 3 — WebView ↔ Native 桥接器（TS 端封装）
// 与 poc/android/.../JsBridge.kt 一一对应。
// 浏览器（非 Android WebView）调用时使用 fallback：navigate / console.warn。

declare global {
  interface Window {
    AndroidBridge?: {
      getJwt(): string;
      getBackendUrl(): string;
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
