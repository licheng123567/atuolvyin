// frontend/src/pages/admin/scripts/__tests__/helpers.test.ts
import { describe, it, expect } from "vitest";
import { getScoreGradeColor, formatAdoptionRate } from "../helpers";

describe("getScoreGradeColor", () => {
  it("returns green for A", () => {
    expect(getScoreGradeColor("A")).toContain("green");
  });
  it("returns blue for B", () => {
    expect(getScoreGradeColor("B")).toContain("blue");
  });
  it("returns orange for C", () => {
    expect(getScoreGradeColor("C")).toContain("orange");
  });
  it("returns red for D", () => {
    expect(getScoreGradeColor("D")).toContain("red");
  });
  it("returns gray for null", () => {
    expect(getScoreGradeColor(null)).toContain("gray");
  });
});

describe("formatAdoptionRate", () => {
  it("formats as percentage", () => {
    expect(formatAdoptionRate(0.753)).toBe("75.3%");
  });
  it("returns dash for null", () => {
    expect(formatAdoptionRate(null)).toBe("—");
  });
});
