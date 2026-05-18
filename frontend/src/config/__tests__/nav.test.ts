import { describe, it, expect } from "vitest";
import { getNavSections, HELP_SECTION } from "../nav";

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

describe("getNavSections — Fix 4 (Gap3): provider supervisor nav", () => {
  it("服务商督导只显示帮助中心，不含会 403 的物业页", () => {
    const sections = getNavSections("supervisor", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    // 不应含物业督导专属页
    expect(paths).not.toContain("/supervisor/live-wall");
    expect(paths).not.toContain("/supervisor/workspace");
    expect(paths).not.toContain("/supervisor/cases");
    expect(paths).not.toContain("/supervisor/discount-approvals");
  });

  it("服务商督导结果等于 [HELP_SECTION]", () => {
    const sections = getNavSections("supervisor", "provider:2");
    expect(sections).toEqual([HELP_SECTION]);
  });

  it("物业督导（tenant scope）仍返回包含实时通话墙的完整 nav — 不误伤", () => {
    const sections = getNavSections("supervisor", "tenant:1");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/supervisor/live-wall");
    expect(paths).toContain("/supervisor/workspace");
  });

  it("物业督导无 scope 参数时也返回完整 nav", () => {
    const sections = getNavSections("supervisor");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/supervisor/live-wall");
  });
});
