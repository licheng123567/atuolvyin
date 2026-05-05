import type { SupervisorAlert } from "../../store/supervisor-alerts";

const PING_INTERVAL_MS = 30_000;

export interface SupervisorSocketHandle {
  close: () => void;
}

export function openSupervisorSocket(opts: {
  token: string;
  baseWsUrl?: string;
  onAlert: (alert: SupervisorAlert) => void;
  onStatusChange?: (status: "connecting" | "connected" | "reconnecting" | "closed") => void;
}): SupervisorSocketHandle {
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  let closedByCaller = false;

  const buildUrl = () => {
    const base =
      opts.baseWsUrl ??
      (window.location.protocol === "https:" ? "wss://" : "ws://") +
        window.location.host;
    const u = new URL(`${base}/ws/supervisor`);
    u.searchParams.set("token", opts.token);
    return u.toString();
  };

  const connect = () => {
    opts.onStatusChange?.(attempts === 0 ? "connecting" : "reconnecting");
    socket = new WebSocket(buildUrl());

    socket.onopen = () => {
      attempts = 0;
      opts.onStatusChange?.("connected");
      pingTimer = setInterval(() => {
        socket?.send(JSON.stringify({ type: "ping" }));
      }, PING_INTERVAL_MS);
    };

    socket.onmessage = (ev) => {
      let msg: { type?: string } & Record<string, unknown>;
      try {
        msg = JSON.parse(ev.data as string);
      } catch {
        return;
      }
      if (msg.type === "supervisor.alert") {
        opts.onAlert({ ...(msg as unknown as SupervisorAlert), read: false });
      }
    };

    socket.onclose = () => {
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (closedByCaller) {
        opts.onStatusChange?.("closed");
        return;
      }
      const delay = Math.min(8_000, 1_000 * Math.pow(2, attempts));
      attempts += 1;
      reconnectTimer = setTimeout(connect, delay);
      opts.onStatusChange?.("reconnecting");
    };
  };

  connect();

  return {
    close() {
      closedByCaller = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      socket?.close();
    },
  };
}
