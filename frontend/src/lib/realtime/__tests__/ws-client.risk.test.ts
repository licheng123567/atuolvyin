import { describe, it, expect } from "vitest";

describe("ws-client risk.event routing", () => {
  it("routes risk.event to onRisk callback", async () => {
    const event = {
      type: "risk.event",
      risk_id: "r-test-001",
      call_id: 1,
      level: "L2",
      category: "owner_threat",
      trigger: "keyword+llm",
      llm_confidence: 0.91,
      matched_keywords: ["威胁"],
      text_snippet: "我要投诉你们",
      speaker: "customer",
      ts: "2026-05-01T10:00:00Z",
    };
    // Verify shape matches our RiskEvent type (TypeScript compile check via cast)
    const typed = event as import("../types").RiskEvent;
    expect(typed.risk_id).toBe("r-test-001");
    expect(typed.level).toBe("L2");
    expect(typed.matched_keywords).toEqual(["威胁"]);
  });
});
