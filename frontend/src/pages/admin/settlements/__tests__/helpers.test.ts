// frontend/src/pages/admin/settlements/__tests__/helpers.test.ts
import { describe, expect, it } from "vitest";
import {
  formatAmount,
  formatPeriod,
  getActionButtons,
  getStatusColor,
  recentYearMonths,
} from "../helpers";

describe("formatPeriod", () => {
  it("formats an ISO start date as YYYY-MM", () => {
    expect(formatPeriod("2026-04-01T00:00:00Z", "2026-04-30T00:00:00Z")).toBe(
      "2026-04",
    );
  });

  it("returns — for empty string", () => {
    expect(formatPeriod("", "")).toBe("—");
  });

  it("returns — for invalid date", () => {
    expect(formatPeriod("not-a-date", "x")).toBe("—");
  });

  it("zero-pads single-digit months", () => {
    expect(formatPeriod("2026-01-15T00:00:00Z", "")).toBe("2026-01");
  });
});

describe("getStatusColor", () => {
  it("returns gray for DRAFT", () => {
    expect(getStatusColor("DRAFT")).toContain("gray");
  });

  it("returns blue for CONFIRMED", () => {
    expect(getStatusColor("CONFIRMED")).toContain("blue");
  });

  it("returns green for PAID", () => {
    expect(getStatusColor("PAID")).toContain("green");
  });

  it("returns red for DISPUTED", () => {
    expect(getStatusColor("DISPUTED")).toContain("red");
  });

  it("falls back for unknown status", () => {
    expect(getStatusColor("UNKNOWN")).toContain("gray");
  });
});

describe("formatAmount", () => {
  it("formats a number with thousand separators and 2 decimals", () => {
    expect(formatAmount(12345.67)).toBe("¥12,345.67");
  });

  it("accepts a string number", () => {
    expect(formatAmount("999.5")).toBe("¥999.50");
  });

  it("returns ¥0.00 for null", () => {
    expect(formatAmount(null)).toBe("¥0.00");
  });

  it("returns ¥0.00 for undefined", () => {
    expect(formatAmount(undefined)).toBe("¥0.00");
  });

  it("returns ¥0.00 for invalid string", () => {
    expect(formatAmount("abc")).toBe("¥0.00");
  });
});

describe("getActionButtons", () => {
  it("returns confirm + dispute for DRAFT", () => {
    const btns = getActionButtons("DRAFT");
    const actions = btns.map((b) => b.action);
    expect(actions).toContain("confirm");
    expect(actions).toContain("dispute");
    expect(actions).not.toContain("pay");
  });

  it("returns pay + dispute for CONFIRMED", () => {
    const btns = getActionButtons("CONFIRMED");
    const actions = btns.map((b) => b.action);
    expect(actions).toContain("pay");
    expect(actions).toContain("dispute");
    expect(actions).not.toContain("confirm");
  });

  it("returns no buttons for PAID", () => {
    expect(getActionButtons("PAID")).toEqual([]);
  });

  it("returns no buttons for DISPUTED in this sprint", () => {
    expect(getActionButtons("DISPUTED")).toEqual([]);
  });
});

describe("recentYearMonths", () => {
  it("returns N entries", () => {
    const from = new Date(Date.UTC(2026, 4, 5)); // May 2026
    expect(recentYearMonths(3, from)).toEqual(["2026-05", "2026-04", "2026-03"]);
  });

  it("rolls back over year boundary", () => {
    const from = new Date(Date.UTC(2026, 1, 5)); // Feb 2026
    const result = recentYearMonths(4, from);
    expect(result).toEqual(["2026-02", "2026-01", "2025-12", "2025-11"]);
  });
});
