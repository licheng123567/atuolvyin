import { describe, it, expect } from "vitest";
import { getNavSections } from "../nav";

describe("getNavSections — provider legal", () => {
  it("returns provider-legal nav for legal role with provider scope", () => {
    const sections = getNavSections("legal", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/provider/legal/cases");
    expect(paths).toContain("/provider/legal/requests");
  });

  it("keeps property-side legal nav for legal role with tenant scope", () => {
    const sections = getNavSections("legal", "tenant:1");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).not.toContain("/provider/legal/cases");
  });
});
