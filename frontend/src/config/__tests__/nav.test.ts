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

describe("getNavSections — provider supervisor nav (Phase 1)", () => {
  it("服务商督导包含 Phase 1 全部九项路径", () => {
    const sections = getNavSections("supervisor", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    // Phase 1 九项
    expect(paths).toContain("/supervisor/workspace");
    expect(paths).toContain("/supervisor/live-wall");
    expect(paths).toContain("/supervisor/team-performance");
    expect(paths).toContain("/supervisor/cases");
    expect(paths).toContain("/supervisor/reviews");
    expect(paths).toContain("/supervisor/script-labels");
    expect(paths).toContain("/supervisor/risk-events");
    expect(paths).toContain("/supervisor/my-kpi");
    expect(paths).toContain("/supervisor/stats");
  });

  it("服务商督导不含明确排除项", () => {
    const sections = getNavSections("supervisor", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    // 明确排除项（Phase 2 已加 /supervisor/shifts，此处不再排除）
    expect(paths).not.toContain("/admin/agent-devices");
    expect(paths).not.toContain("/supervisor/escalated");
    expect(paths).not.toContain("/supervisor/promises");
    expect(paths).not.toContain("/supervisor/case-alerts");
    expect(paths).not.toContain("/supervisor/discount-approvals");
    expect(paths).not.toContain("/supervisor/legal-conversion-approvals");
    expect(paths).not.toContain("/supervisor/training");
  });

  it("provider supervisor nav 含值班排班（Phase 2）", () => {
    const paths = getNavSections("supervisor", "provider:2")
      .flatMap((s) => s.items)
      .map((i) => i.path);
    expect(paths).toContain("/supervisor/shifts");
  });

  it("服务商督导仍包含 HELP_SECTION", () => {
    const sections = getNavSections("supervisor", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/help/app");
  });

  it("物业督导（tenant scope）仍返回包含实时通话墙的完整 nav — 不误伤", () => {
    const sections = getNavSections("supervisor", "tenant:1");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/supervisor/live-wall");
    expect(paths).toContain("/supervisor/workspace");
    // 物业督导有排班
    expect(paths).toContain("/supervisor/shifts");
  });

  it("物业督导无 scope 参数时也返回完整 nav", () => {
    const sections = getNavSections("supervisor");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/supervisor/live-wall");
    expect(paths).toContain("/supervisor/shifts");
  });
});
