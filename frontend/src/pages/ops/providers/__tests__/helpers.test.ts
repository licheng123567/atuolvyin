// frontend/src/pages/ops/providers/__tests__/helpers.test.ts
import { describe, expect, it } from "vitest";
import {
  daysUntil,
  formatAuditStatus,
  formatProviderType,
  getAuditStatusColor,
  getTrialUrgencyColor,
} from "../helpers";

describe("getAuditStatusColor", () => {
  it("returns yellow for pending", () => {
    expect(getAuditStatusColor("pending")).toContain("yellow");
  });

  it("returns green for approved", () => {
    expect(getAuditStatusColor("approved")).toContain("green");
  });

  it("returns red for rejected", () => {
    expect(getAuditStatusColor("rejected")).toContain("red");
  });

  it("falls back to gray for unknown", () => {
    expect(getAuditStatusColor("frobnicated")).toContain("gray");
  });
});

describe("formatAuditStatus", () => {
  it("localises known statuses", () => {
    expect(formatAuditStatus("pending")).toBe("待审核");
    expect(formatAuditStatus("approved")).toBe("已通过");
    expect(formatAuditStatus("rejected")).toBe("已驳回");
  });

  it("passes through unknown value", () => {
    expect(formatAuditStatus("xyz")).toBe("xyz");
  });
});

describe("formatProviderType", () => {
  it("localises known types", () => {
    expect(formatProviderType("legal")).toBe("法务");
    expect(formatProviderType("collection")).toBe("催收");
    expect(formatProviderType("both")).toBe("法务+催收");
  });

  it("passes through unknown type", () => {
    expect(formatProviderType("other")).toBe("other");
  });
});

describe("daysUntil", () => {
  const now = new Date("2026-05-05T00:00:00Z");

  it("returns null for falsy input", () => {
    expect(daysUntil(null, now)).toBeNull();
    expect(daysUntil(undefined, now)).toBeNull();
    expect(daysUntil("", now)).toBeNull();
  });

  it("returns null for invalid date", () => {
    expect(daysUntil("not-a-date", now)).toBeNull();
  });

  it("computes days until a future date (ceil)", () => {
    expect(daysUntil("2026-05-15T00:00:00Z", now)).toBe(10);
  });

  it("returns 0 for past dates", () => {
    expect(daysUntil("2026-04-01T00:00:00Z", now)).toBe(0);
  });

  it("rounds partial days up", () => {
    // 36h ≈ 1.5 day → ceil to 2
    expect(daysUntil("2026-05-06T12:00:00Z", now)).toBe(2);
  });
});

describe("getTrialUrgencyColor", () => {
  it("returns red for <=3 days", () => {
    expect(getTrialUrgencyColor(0)).toContain("red");
    expect(getTrialUrgencyColor(3)).toContain("red");
  });

  it("returns yellow for 4..7 days", () => {
    expect(getTrialUrgencyColor(4)).toContain("yellow");
    expect(getTrialUrgencyColor(7)).toContain("yellow");
  });

  it("returns gray for >7 days", () => {
    expect(getTrialUrgencyColor(30)).toContain("gray");
  });

  it("returns gray for null", () => {
    expect(getTrialUrgencyColor(null)).toContain("gray");
  });
});
