// Sprint 14.2 — 实时通话墙 store (PRD §11.6)
import { create } from "zustand";

export interface LiveCall {
  call_id: number;
  case_id: number | null;
  caller_user_id: number;
  caller_name: string;
  owner_name: string | null;
  owner_phone_masked: string | null;
  started_at: string | null;
  last_heartbeat_at: string | null;
  duration_sec: number;
  recording_mode: string;
  status: "dialing" | "live" | "aborted" | "live_ended_pending_analysis" | string;
  risk_flagged: boolean;
}

export interface CallEvent {
  type: "call.started" | "call.ended" | "call.aborted";
  call_id: number;
  case_id: number | null;
  caller_user_id: number;
  caller_name: string | null;
  owner_name: string | null;
  owner_phone_masked: string | null;
  started_at: string | null;
  recording_mode: string;
  status: string;
}

interface LiveCallState {
  calls: LiveCall[];
  setInitial: (items: LiveCall[]) => void;
  applyEvent: (evt: CallEvent) => void;
  remove: (callId: number) => void;
}

export const useLiveCallStore = create<LiveCallState>((set, get) => ({
  calls: [],
  setInitial: (items) => set({ calls: items }),
  applyEvent: (evt) => {
    const list = get().calls;
    if (evt.type === "call.started") {
      if (list.some((c) => c.call_id === evt.call_id)) return;
      set({
        calls: [
          {
            call_id: evt.call_id,
            case_id: evt.case_id,
            caller_user_id: evt.caller_user_id,
            caller_name: evt.caller_name ?? "未知坐席",
            owner_name: evt.owner_name,
            owner_phone_masked: evt.owner_phone_masked,
            started_at: evt.started_at,
            last_heartbeat_at: evt.started_at,
            duration_sec: 0,
            recording_mode: evt.recording_mode,
            status: evt.status,
            risk_flagged: false,
          },
          ...list,
        ],
      });
    } else {
      // ended / aborted
      set({ calls: list.filter((c) => c.call_id !== evt.call_id) });
    }
  },
  remove: (callId) =>
    set((s) => ({ calls: s.calls.filter((c) => c.call_id !== callId) })),
}));
