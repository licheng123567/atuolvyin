import { describe, expect, it } from "vitest";
import {
  LEGAL_STAGES,
  LEGAL_STAGE_LABELS,
  formatStage,
  getStageColor,
  isClosedStage,
} from "../helpers";

describe("LEGAL_STAGES", () => {
  it("includes all 8 expected stages", () => {
    expect(LEGAL_STAGES).toHaveLength(8);
    expect(LEGAL_STAGES).toContain("pending_eval");
    expect(LEGAL_STAGES).toContain("evidence_collection");
    expect(LEGAL_STAGES).toContain("litigation_filed");
    expect(LEGAL_STAGES).toContain("judgment_pending");
    expect(LEGAL_STAGES).toContain("enforcing");
    expect(LEGAL_STAGES).toContain("closed_won");
    expect(LEGAL_STAGES).toContain("closed_lost");
    expect(LEGAL_STAGES).toContain("closed_settled");
  });

  it("has a Chinese label for each stage", () => {
    for (const stage of LEGAL_STAGES) {
      expect(LEGAL_STAGE_LABELS[stage]).toBeTruthy();
      expect(LEGAL_STAGE_LABELS[stage].length).toBeGreaterThan(0);
    }
  });
});

describe("formatStage", () => {
  it("returns Chinese label for known stages", () => {
    expect(formatStage("pending_eval")).toBe("待评估");
    expect(formatStage("evidence_collection")).toBe("取证中");
    expect(formatStage("closed_won")).toBe("胜诉结案");
  });

  it("falls back to raw value for unknown stages", () => {
    expect(formatStage("future_stage_v2")).toBe("future_stage_v2");
    expect(formatStage("")).toBe("");
  });
});

describe("getStageColor", () => {
  it("returns object with background and color for known stages", () => {
    const colors = getStageColor("evidence_collection");
    expect(colors.background).toBeTruthy();
    expect(colors.color).toBeTruthy();
  });

  it("returns neutral colors for unknown stages", () => {
    const colors = getStageColor("totally_unknown");
    expect(colors.background).toContain("neutral");
  });

  it("differentiates closed_won (success) from closed_lost (danger)", () => {
    const won = getStageColor("closed_won");
    const lost = getStageColor("closed_lost");
    expect(won.color).not.toEqual(lost.color);
  });
});

describe("isClosedStage", () => {
  it("flags closed_won, closed_lost, and closed_settled", () => {
    expect(isClosedStage("closed_won")).toBe(true);
    expect(isClosedStage("closed_lost")).toBe(true);
    expect(isClosedStage("closed_settled")).toBe(true);
  });

  it("returns false for in-progress stages", () => {
    expect(isClosedStage("pending_eval")).toBe(false);
    expect(isClosedStage("evidence_collection")).toBe(false);
    expect(isClosedStage("litigation_filed")).toBe(false);
    expect(isClosedStage("enforcing")).toBe(false);
  });

  it("returns false for unknown stages", () => {
    expect(isClosedStage("xxx")).toBe(false);
    expect(isClosedStage("")).toBe(false);
  });
});
