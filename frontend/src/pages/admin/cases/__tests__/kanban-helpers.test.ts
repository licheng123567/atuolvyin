// frontend/src/pages/admin/cases/__tests__/kanban-helpers.test.ts
import { describe, it, expect } from "vitest";
import { groupByStage, STAGES, STAGE_LABELS } from "../kanban-helpers";

describe("STAGES constant", () => {
  it("contains all 6 expected stages", () => {
    expect(STAGES).toHaveLength(6);
    expect(STAGES).toContain("new");
    expect(STAGES).toContain("in_progress");
    expect(STAGES).toContain("promised");
    expect(STAGES).toContain("paid");
    expect(STAGES).toContain("escalated");
    expect(STAGES).toContain("closed");
  });
});

describe("STAGE_LABELS", () => {
  it("has a label for each stage", () => {
    for (const stage of STAGES) {
      expect(STAGE_LABELS[stage]).toBeTruthy();
    }
  });
});

describe("groupByStage", () => {
  it("returns all 6 buckets empty given an empty array", () => {
    const groups = groupByStage([]);
    for (const stage of STAGES) {
      expect(groups[stage]).toEqual([]);
    }
  });

  it("groups single item into correct bucket", () => {
    const item = { id: 1, stage: "new" };
    const groups = groupByStage([item]);
    expect(groups.new).toHaveLength(1);
    expect(groups.new[0]).toBe(item);
    // all other buckets are empty
    expect(groups.in_progress).toHaveLength(0);
    expect(groups.promised).toHaveLength(0);
    expect(groups.paid).toHaveLength(0);
    expect(groups.escalated).toHaveLength(0);
    expect(groups.closed).toHaveLength(0);
  });

  it("groups multiple items across multiple stages", () => {
    const items = [
      { id: 1, stage: "new" },
      { id: 2, stage: "in_progress" },
      { id: 3, stage: "in_progress" },
      { id: 4, stage: "paid" },
      { id: 5, stage: "closed" },
    ];
    const groups = groupByStage(items);
    expect(groups.new).toHaveLength(1);
    expect(groups.in_progress).toHaveLength(2);
    expect(groups.promised).toHaveLength(0);
    expect(groups.paid).toHaveLength(1);
    expect(groups.escalated).toHaveLength(0);
    expect(groups.closed).toHaveLength(1);
  });

  it("does not crash on unknown stage values — they are silently ignored", () => {
    const items = [
      { id: 1, stage: "unknown_future_stage" },
      { id: 2, stage: "new" },
      { id: 3, stage: "" },
    ];
    expect(() => groupByStage(items)).not.toThrow();
    const groups = groupByStage(items);
    expect(groups.new).toHaveLength(1);
    // unknown stages should not appear in any bucket
    const totalGrouped = STAGES.reduce((n, s) => n + groups[s].length, 0);
    expect(totalGrouped).toBe(1); // only the "new" item
  });

  it("preserves original object references", () => {
    const item = { id: 42, stage: "escalated", extra: "data" };
    const groups = groupByStage([item]);
    expect(groups.escalated[0]).toBe(item);
  });

  it("handles all stages populated simultaneously", () => {
    const items = STAGES.map((stage, i) => ({ id: i, stage }));
    const groups = groupByStage(items);
    for (const stage of STAGES) {
      expect(groups[stage]).toHaveLength(1);
      expect(groups[stage][0].stage).toBe(stage);
    }
  });
});
