import { describe, it, expect } from "vitest";
import { isPlatformPreset } from "../helpers";

describe("isPlatformPreset", () => {
  it("returns true when tenant_id is null", () => {
    expect(isPlatformPreset({ tenant_id: null })).toBe(true);
  });

  it("returns false when tenant_id is set", () => {
    expect(isPlatformPreset({ tenant_id: 1 })).toBe(false);
  });
});
