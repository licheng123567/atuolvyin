import { describe, expect, it } from "vitest";
import {
  WORK_ORDER_STATUSES,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_TYPES,
  WORK_ORDER_TYPE_LABELS,
  formatStatus,
  formatType,
  getStatusColor,
  isTerminalStatus,
} from "../helpers";

describe("WORK_ORDER_STATUSES", () => {
  it("contains the 4 expected lifecycle statuses", () => {
    expect(WORK_ORDER_STATUSES).toEqual([
      "open",
      "in_progress",
      "resolved",
      "closed",
    ]);
  });

  it("has Chinese labels for all statuses", () => {
    for (const s of WORK_ORDER_STATUSES) {
      expect(WORK_ORDER_STATUS_LABELS[s]).toBeTruthy();
    }
  });
});

describe("WORK_ORDER_TYPES", () => {
  it("contains all 4 order types", () => {
    expect(WORK_ORDER_TYPES).toEqual([
      "quality",
      "reduction",
      "dispute",
      "other",
    ]);
  });

  it("has Chinese labels for each type", () => {
    for (const t of WORK_ORDER_TYPES) {
      expect(WORK_ORDER_TYPE_LABELS[t]).toBeTruthy();
    }
  });
});

describe("formatStatus / formatType", () => {
  it("translates known statuses", () => {
    expect(formatStatus("open")).toBe("待处理");
    expect(formatStatus("in_progress")).toBe("处理中");
    expect(formatStatus("resolved")).toBe("已解决");
    expect(formatStatus("closed")).toBe("已关闭");
  });

  it("returns the raw value for unknown statuses", () => {
    expect(formatStatus("paused")).toBe("paused");
  });

  it("translates known order types", () => {
    expect(formatType("quality")).toBe("服务质量");
    expect(formatType("reduction")).toBe("减免申请");
  });

  it("returns the raw value for unknown order types", () => {
    expect(formatType("escalation")).toBe("escalation");
  });
});

describe("getStatusColor", () => {
  it("returns colors for known statuses", () => {
    expect(getStatusColor("open").background).toBeTruthy();
    expect(getStatusColor("in_progress").color).toBeTruthy();
  });

  it("returns neutral colors for unknown statuses", () => {
    expect(getStatusColor("xxx").background).toContain("neutral");
  });
});

describe("isTerminalStatus", () => {
  it("returns true for resolved/closed", () => {
    expect(isTerminalStatus("resolved")).toBe(true);
    expect(isTerminalStatus("closed")).toBe(true);
  });

  it("returns false for in-progress statuses", () => {
    expect(isTerminalStatus("open")).toBe(false);
    expect(isTerminalStatus("in_progress")).toBe(false);
  });
});
