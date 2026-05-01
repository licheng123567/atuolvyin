// frontend/src/lib/realtime/ws-client.ts
import type {
  CallSocketHandle,
  CallSocketOptions,
  CallSocketStatus,
  TranscriptChunk,
  Suggestion,
  TagPayload,
} from "./types";

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 8_000;

function buildUrl(opts: CallSocketOptions): string {
  const base = opts.baseWsUrl ??
    (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  const u = new URL(`${base}/ws/calls/${opts.callId}`);
  u.searchParams.set("token", opts.token);
  u.searchParams.set("role", opts.role);
  return u.toString();
}

export function openCallSocket(opts: CallSocketOptions): CallSocketHandle {
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  let closedByCaller = false;

  const setStatus = (s: CallSocketStatus) => opts.onStatusChange?.(s);

  const connect = () => {
    setStatus(attempts === 0 ? "connecting" : "reconnecting");
    socket = new WebSocket(buildUrl(opts));

    socket.onopen = () => {
      attempts = 0;
      setStatus("connected");
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
      switch (msg.type) {
        case "transcript.chunk":
          opts.onTranscript?.(msg as unknown as TranscriptChunk);
          break;
        case "suggestion.ready":
          opts.onSuggestion?.(msg as unknown as Suggestion);
          break;
        case "tag.ready":
          opts.onTagReady?.(msg as unknown as TagPayload);
          break;
        case "pong":
        case "ack":
          break;
      }
    };

    socket.onerror = () => {
      // onclose will follow; do reconnect there
    };

    socket.onclose = () => {
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (closedByCaller) {
        setStatus("call_ended");
        return;
      }
      const delay = Math.min(MAX_BACKOFF_MS, 1000 * Math.pow(2, attempts));
      attempts += 1;
      reconnectTimer = setTimeout(connect, delay);
      setStatus("reconnecting");
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
    sendFeedback(suggestionId, action) {
      socket?.send(JSON.stringify({ type: "suggestion.feedback", id: suggestionId, action }));
    },
  };
}
