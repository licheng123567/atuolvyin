// frontend/src/pages/provider/__tests__/helpers.test.ts
import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatRevenue,
  getContractStatusColor,
  getContractStatusLabel,
  recentYearMonths,
} from "../helpers";

describe("formatRevenue", () => {
  it("formats a positive number as ¥X.XX", () => {
    expect(formatRevenue(1234.5)).toBe("¥1,234.50");
  });

  it("accepts numeric strings (Decimal from backend)", () => {
    expect(formatRevenue("5000.00")).toBe("¥5,000.00");
  });

  it("falls back to ¥0.00 for null", () => {
    expect(formatRevenue(null)).toBe("¥0.00");
  });

  it("falls back to ¥0.00 for empty string", () => {
    expect(formatRevenue("")).toBe("¥0.00");
  });

  it("falls back to ¥0.00 for NaN", () => {
    expect(formatRevenue("not-a-number")).toBe("¥0.00");
  });
});

describe("getContractStatusColor", () => {
  it("returns green for active", () => {
    expect(getContractStatusColor("active")).toContain("green");
  });

  it("returns red for terminated", () => {
    expect(getContractStatusColor("terminated")).toContain("red");
  });

  it("returns gray for expired", () => {
    expect(getContractStatusColor("expired")).toContain("gray");
  });

  it("falls back to gray on unknown", () => {
    expect(getContractStatusColor("frobozz")).toContain("gray");
  });
});

describe("getContractStatusLabel", () => {
  it("translates active to 履约中", () => {
    expect(getContractStatusLabel("active")).toBe("履约中");
  });

  it("returns input unchanged when unknown", () => {
    expect(getContractStatusLabel("custom_state")).toBe("custom_state");
  });
});

describe("formatDate", () => {
  it("formats an ISO date as YYYY-MM-DD", () => {
    expect(formatDate("2026-04-15T08:00:00Z")).toBe("2026-04-15");
  });

  it("returns — for empty", () => {
    expect(formatDate("")).toBe("—");
  });

  it("returns — for invalid", () => {
    expect(formatDate("nope")).toBe("—");
  });
});

describe("recentYearMonths", () => {
  it("returns n options newest-first", () => {
    const res = recentYearMonths(3, new Date(Date.UTC(2026, 4, 5)));
    // May 2026 → [2026-05, 2026-04, 2026-03]
    expect(res).toEqual(["2026-05", "2026-04", "2026-03"]);
  });
});
