import { describe, it, expect } from "vitest";
import { getRiskAnnotationForSegment } from "../detail";

describe("getRiskAnnotationForSegment", () => {
  const risks = [
    {
      risk_id: "r-001",
      level: "L2",
      category: "owner_threat",
      trigger: "keyword+llm",
      text_snippet: "我要投诉你们",
      matched_keywords: ["投诉"],
      llm_confidence: 0.91,
      speaker: "customer",
    },
  ];

  it("returns annotation when segment text contains risk snippet", () => {
    const annotation = getRiskAnnotationForSegment("我要投诉你们，你们等着", risks);
    expect(annotation).not.toBeNull();
    expect(annotation?.category).toBe("owner_threat");
    expect(annotation?.level).toBe("L2");
  });

  it("returns null when segment text has no overlap with any risk", () => {
    const annotation = getRiskAnnotationForSegment("今天天气不错", risks);
    expect(annotation).toBeNull();
  });

  it("returns null when risks array is empty", () => {
    const annotation = getRiskAnnotationForSegment("我要投诉你们", []);
    expect(annotation).toBeNull();
  });
});
