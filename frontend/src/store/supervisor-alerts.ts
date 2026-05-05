import { create } from "zustand";

export interface SupervisorAlert {
  type: "supervisor.alert";
  risk_id: string;
  call_id: number;
  agent_name: string;
  case_id: number;
  level: "L1" | "L2";
  category: "owner_abuse" | "owner_threat" | "agent_violation" | "agent_minor_misconduct";
  trigger: "keyword_only" | "llm_only" | "keyword+llm";
  llm_confidence: number;
  matched_keywords: string[];
  text_snippet: string;
  speaker: "agent" | "customer";
  ts: string;
  read: boolean;
}

interface SupervisorAlertState {
  alerts: SupervisorAlert[];
  unreadCount: number;
  addAlert: (alert: SupervisorAlert) => void;
  markRead: (riskId: string) => void;
  clearAll: () => void;
}

export const useSupervisorAlertStore = create<SupervisorAlertState>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  addAlert: (alert) => {
    const existing = get().alerts;
    if (existing.some((a) => a.risk_id === alert.risk_id)) return;
    set((s) => ({
      alerts: [alert, ...s.alerts],
      unreadCount: s.unreadCount + (alert.read ? 0 : 1),
    }));
  },
  markRead: (riskId) => {
    set((s) => ({
      alerts: s.alerts.map((a) =>
        a.risk_id === riskId ? { ...a, read: true } : a
      ),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }));
  },
  clearAll: () => set({ alerts: [], unreadCount: 0 }),
}));
