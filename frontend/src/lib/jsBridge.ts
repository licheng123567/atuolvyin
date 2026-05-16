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
      // v2.3 Module 2 — 录音目录手选
      openRecordingDirPicker?(): void;
      getRecordingDirUri?(): string;
      // v0.5.2 — 当前 ROM 推荐的录音目录（基于 RecordingScanner 22 候选 + 命中检测）
      getSuggestedRecordingDir?(): string;
      // v0.5.2 — React 登录成功后把 JWT 推回 native（替代 Compose AlertDialog 登录）
      saveJwt?(token: string): void;
      // v2.4 — In-call 红色挂断按钮调用：尝试 native endCall + 跳到 call-end
      endCall?(callId: number): void;
      // v2.4 — call-end / force-logout 提交完成后退出 fullscreen overlay 回 4-tab
      exitOverlay?(): void;
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

  // v2.3 Module 2 — 触发 native SAF 文件夹选择器修改录音上传目录
  openRecordingDirPicker: (): void => {
    if (window.AndroidBridge?.openRecordingDirPicker) {
      window.AndroidBridge.openRecordingDirPicker();
    } else {
      // 浏览器 fallback
      // eslint-disable-next-line no-alert
      window.alert("此功能仅在 App 内可用");
    }
  },

  // v2.3 Module 2 — 当前录音文件夹 URI（friendly path 或空串）
  getRecordingDirUri: (): string => {
    if (typeof window === "undefined") return "";
    return window.AndroidBridge?.getRecordingDirUri?.() ?? "";
  },

  // v0.5.2 — 当前 ROM 推荐的录音目录路径（如 "MIUI/sound_recorder/call_rec"）
  // 用于 Profile 引导文案，告诉用户「本机推荐目录」
  getSuggestedRecordingDir: (): string => {
    if (typeof window === "undefined") return "";
    return window.AndroidBridge?.getSuggestedRecordingDir?.() ?? "";
  },

  // v0.5.2 — React 登录成功后把 JWT 推给 native（让 CallWatcherService / ApiClient 拿到）。
  // 浏览器路径无 native 端，no-op 即可。
  saveJwt: (token: string): void => {
    window.AndroidBridge?.saveJwt?.(token);
  },

  // v2.4 — In-call 挂断按钮触发：native 试图结束系统通话（API 28+ 才有效），
  // 然后无论成功与否都让 WebView 跳到 /app/call-end/{id} 让坐席填标记。
  // 浏览器 fallback：直接 navigate 到 call-end（无 native 通话需结束）。
  endCall: (callId: number): void => {
    if (window.AndroidBridge?.endCall) {
      window.AndroidBridge.endCall(callId);
    } else {
      // 浏览器/无 bridge：no-op；调用方应自行 navigate 到 call-end
      // eslint-disable-next-line no-console
      console.warn("[browser] would endCall", callId);
    }
  },

  // v2.4 — call-end / force-logout 提交完毕通知 native 关闭 fullscreen overlay。
  // 浏览器 fallback：no-op。
  exitOverlay: (): void => {
    window.AndroidBridge?.exitOverlay?.();
  },
};

export {};
