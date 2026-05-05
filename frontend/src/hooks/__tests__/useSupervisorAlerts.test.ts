import { describe, it, expect, beforeEach } from "vitest";
import { useSupervisorAlertStore } from "../../store/supervisor-alerts";

describe("supervisor-alerts Zustand store", () => {
  beforeEach(() => {
    useSupervisorAlertStore.getState().clearAll();
  });

  it("starts with empty alerts", () => {
    expect(useSupervisorAlertStore.getState().alerts).toHaveLength(0);
  });

  it("addAlert appends to alerts", () => {
    const alert = {
      type: "supervisor.alert" as const,
      risk_id: "r-001",
      call_id: 1,
      agent_name: "王催收",
      case_id: 10,
      level: "L2" as const,
      category: "owner_threat" as const,
      trigger: "keyword+llm" as const,
      llm_confidence: 0.91,
      matched_keywords: ["威胁"],
      text_snippet: "我要投诉",
      speaker: "customer" as const,
      ts: "2026-05-01T10:00:00Z",
      read: false,
    };
    useSupervisorAlertStore.getState().addAlert(alert);
    expect(useSupervisorAlertStore.getState().alerts).toHaveLength(1);
    expect(useSupervisorAlertStore.getState().unreadCount).toBe(1);
  });

  it("markRead reduces unreadCount", () => {
    useSupervisorAlertStore.getState().addAlert({
      type: "supervisor.alert",
      risk_id: "r-002",
      call_id: 2,
      agent_name: "李催收",
      case_id: 20,
      level: "L2",
      category: "owner_threat",
      trigger: "keyword_only",
      llm_confidence: 0,
      matched_keywords: [],
      text_snippet: "test",
      speaker: "customer",
      ts: "2026-05-01T11:00:00Z",
      read: false,
    });
    useSupervisorAlertStore.getState().markRead("r-002");
    expect(useSupervisorAlertStore.getState().unreadCount).toBe(0);
  });

  it("clearAll empties alerts", () => {
    useSupervisorAlertStore.getState().addAlert({
      type: "supervisor.alert",
      risk_id: "r-003",
      call_id: 3,
      agent_name: "张催收",
      case_id: 30,
      level: "L1",
      category: "owner_abuse",
      trigger: "keyword_only",
      llm_confidence: 0,
      matched_keywords: [],
      text_snippet: "test",
      speaker: "customer",
      ts: "2026-05-01T12:00:00Z",
      read: false,
    });
    useSupervisorAlertStore.getState().clearAll();
    expect(useSupervisorAlertStore.getState().alerts).toHaveLength(0);
  });
});
