// frontend/src/pages/admin/dashboard/__tests__/helpers.test.ts
import { describe, it, expect } from "vitest";
import {
  formatMinutes,
  getQuotaWarning,
  formatRate,
  formatCurrency,
} from "../helpers";

describe("formatMinutes", () => {
  it("returns — for null", () => {
    expect(formatMinutes(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatMinutes(undefined)).toBe("—");
  });

  it("formats zero as 0", () => {
    expect(formatMinutes(0)).toBe("0");
  });

  it("formats a normal integer", () => {
    // toLocaleString may differ by locale, but the number should appear
    const result = formatMinutes(1234);
    expect(result).toMatch(/1[,.]?234/);
  });

  it("formats large number", () => {
    const result = formatMinutes(10000);
    expect(result).toMatch(/10[,.]?000/);
  });
});

describe("getQuotaWarning", () => {
  it("returns ok when total is null", () => {
    expect(getQuotaWarning(9999, null)).toBe("ok");
  });

  it("returns ok when ratio < 0.8", () => {
    expect(getQuotaWarning(700, 1000)).toBe("ok");
  });

  it("returns warn when ratio is exactly 0.8", () => {
    expect(getQuotaWarning(800, 1000)).toBe("warn");
  });

  it("returns warn when ratio is between 0.8 and 1", () => {
    expect(getQuotaWarning(900, 1000)).toBe("warn");
  });

  it("returns danger when ratio is exactly 1", () => {
    expect(getQuotaWarning(1000, 1000)).toBe("danger");
  });

  it("returns danger when ratio > 1", () => {
    expect(getQuotaWarning(1200, 1000)).toBe("danger");
  });
});

describe("formatRate", () => {
  it("returns — for null", () => {
    expect(formatRate(null)).toBe("—");
  });

  it("returns — for undefined", () => {
    expect(formatRate(undefined)).toBe("—");
  });

  it("formats 0 correctly", () => {
    expect(formatRate(0)).toBe("0.0%");
  });

  it("formats 0.5 as 50.0%", () => {
    expect(formatRate(0.5)).toBe("50.0%");
  });

  it("formats 1.0 as 100.0%", () => {
    expect(formatRate(1.0)).toBe("100.0%");
  });

  it("rounds to 1 decimal place", () => {
    expect(formatRate(0.756)).toBe("75.6%");
  });
});

describe("formatCurrency", () => {
  it("formats 0 as ¥0", () => {
    expect(formatCurrency(0)).toBe("¥0");
  });

  it("formats a positive integer", () => {
    const result = formatCurrency(1000);
    expect(result).toMatch(/^¥1[,.]?000$/);
  });

  it("formats large number with thousands separator", () => {
    const result = formatCurrency(89400);
    expect(result).toMatch(/^¥89[,.]?400$/);
  });

  it("formats negative number", () => {
    const result = formatCurrency(-500);
    expect(result).toContain("500");
    expect(result).toContain("¥");
  });
});
