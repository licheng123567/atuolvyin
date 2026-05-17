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
    // 正向断言：物业侧 legal 必须包含内部处理主入口，确认未被误伤
    expect(paths).toContain("/legal/internal-orders");
    // 负向断言：不应包含服务商法务路径
    expect(paths).not.toContain("/provider/legal/cases");
  });

  it("provider scope for non-legal role does not include /provider/legal/cases", () => {
    // supervisor 角色在 provider scope 下，role !== "legal"，不应触发 LEGAL_PROVIDER_NAV 分支
    const sections = getNavSections("supervisor", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).not.toContain("/provider/legal/cases");
  });
});
