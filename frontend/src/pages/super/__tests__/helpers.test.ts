import { describe, expect, it } from "vitest";
import {
  formatLatency,
  formatMinutes,
  formatPercent,
  formatPrice,
  getStatusDotColor,
} from "../helpers";

describe("formatLatency", () => {
  it("returns — for null", () => {
    expect(formatLatency(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatLatency(undefined)).toBe("—");
  });

  it("returns <1 ms for 0", () => {
    expect(formatLatency(0)).toBe("<1 ms");
  });

  it("appends ms suffix", () => {
    expect(formatLatency(42)).toBe("42 ms");
  });
});

describe("getStatusDotColor", () => {
  it("returns green for ok", () => {
    expect(getStatusDotColor("ok")).toContain("green");
  });

  it("returns yellow for degraded", () => {
    expect(getStatusDotColor("degraded")).toContain("yellow");
  });

  it("returns red for down", () => {
    expect(getStatusDotColor("down")).toContain("red");
  });

  it("falls back to gray for unknown", () => {
    expect(getStatusDotColor("unknown")).toContain("gray");
  });
});

describe("formatPercent", () => {
  it("formats with 1 decimal by default", () => {
    expect(formatPercent(33.456)).toBe("33.5%");
  });

  it("respects digits argument", () => {
    expect(formatPercent(33.456, 2)).toBe("33.46%");
  });

  it("returns — for null", () => {
    expect(formatPercent(null)).toBe("—");
  });

  it("returns — for NaN", () => {
    expect(formatPercent(Number.NaN)).toBe("—");
  });
});

describe("formatMinutes", () => {
  it("formats 1234 with separator", () => {
    expect(formatMinutes(1234)).toBe("1,234");
  });

  it("returns — for null", () => {
    expect(formatMinutes(null)).toBe("—");
  });
});

describe("formatPrice", () => {
  it("formats numeric value", () => {
    expect(formatPrice(99)).toBe("¥99.00");
  });

  it("formats string value", () => {
    expect(formatPrice("299.50")).toBe("¥299.50");
  });

  it("returns — for null", () => {
    expect(formatPrice(null)).toBe("—");
  });
});
