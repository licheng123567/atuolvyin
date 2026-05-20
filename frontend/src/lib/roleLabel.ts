// v0.5.6 — 统一 role → 中文显示文案的单一事实源(SSOT)。
// 在此之前散落 10+ 个文件,每个文件都本地定义 ROLE_LABEL = { admin: "管理员", ... }
// 问题:admin 默认翻译为「管理员」无法区分平台超管 / OPS / 服务商 admin / 物业 admin。
// v0.5.6 起统一:tenant.admin = 物业管理员、provider.admin = 服务商管理员、
// platform.superadmin = 平台超管、platform.ops = 平台运营。
//
// 用法:
//   import { roleLabel } from "@/lib/roleLabel";
//   const text = roleLabel("admin", "tenant");  // "物业管理员"
//   const text = roleLabel("agent", "provider"); // "服务商催收员"
//   const text = roleLabel("superadmin", "platform"); // "平台超管"
//
// 注意:本函数只负责对外展示文案。代码逻辑里的 role 比较(如 role === "admin")
// 不要用本函数,直接用 role 字符串字面量。

export type RoleScope = "tenant" | "provider" | "platform";

const TENANT_ROLES = {
  admin: "物业管理员",
  supervisor: "督导",
  agent: "催收员",
  legal: "法务对接人",
  coordinator: "运营协调",
  project_manager: "项目负责人",
} as const;

const PROVIDER_ROLES = {
  admin: "服务商管理员",
  supervisor: "服务商督导",
  agent: "服务商催收员",
  legal: "服务商法务",
  project_manager: "服务商项目负责人",
  coordinator: "服务商运营协调",
} as const;

const PLATFORM_ROLES = {
  superadmin: "平台超管",
  ops: "平台运营",
} as const;

const MAP: Record<RoleScope, Record<string, string>> = {
  tenant: TENANT_ROLES,
  provider: PROVIDER_ROLES,
  platform: PLATFORM_ROLES,
};

/**
 * 把 role 字符串(后端原始值)翻译成对外中文显示文案。
 *
 * @param role  后端 role 值(如 "admin" / "agent" / "superadmin")
 * @param scope 角色所属作用域 — 物业(tenant)/ 服务商(provider)/ 平台(platform)。
 *              默认 tenant。
 * @returns     中文显示文案;未识别的 role 直接原样返回。
 */
export function roleLabel(role: string, scope: RoleScope = "tenant"): string {
  return MAP[scope]?.[role] ?? role;
}

/**
 * v0.5.6 — 根据 membership 自动推导 scope。
 * 用法:
 *   roleLabelFromMembership({ role: "admin", provider_id: 5 })  // "服务商管理员"
 *   roleLabelFromMembership({ role: "admin", provider_id: null }) // "物业管理员"
 */
export function roleLabelFromMembership(m: {
  role: string;
  provider_id?: number | null;
}): string {
  const scope: RoleScope = m.provider_id ? "provider" : "tenant";
  return roleLabel(m.role, scope);
}

/**
 * v0.5.6 — 平台用户(无 membership,只有 platform_role)的便捷封装。
 *   roleLabelPlatform("superadmin")  // "平台超管"
 *   roleLabelPlatform("ops")         // "平台运营"
 */
export function roleLabelPlatform(platformRole: string): string {
  return roleLabel(platformRole, "platform");
}

/**
 * v0.5.6 — 不知道 scope 时按优先级 platform > tenant > provider 兜底查找。
 * 用于审计日志 / 跨域用户列表等需要展示「任意 scope 角色」的场景。
 *   roleLabelAny("superadmin")  // "平台超管"
 *   roleLabelAny("admin")       // "物业管理员"(tenant 优先)
 *   roleLabelAny("agent")       // "催收员"(tenant 优先)
 */
export function roleLabelAny(role: string): string {
  return (
    PLATFORM_ROLES[role as keyof typeof PLATFORM_ROLES] ??
    TENANT_ROLES[role as keyof typeof TENANT_ROLES] ??
    PROVIDER_ROLES[role as keyof typeof PROVIDER_ROLES] ??
    role
  );
}

/**
 * v0.5.6 — 从 AuthUser.scope 字符串("tenant:1" / "provider:2" / "platform")推导 RoleScope。
 * 用法:
 *   roleLabelFromUser({ role: "admin", scope: "provider:5" })  // "服务商管理员"
 *   roleLabelFromUser({ role: "admin", scope: "tenant:1" })    // "物业管理员"
 *   roleLabelFromUser({ role: "superadmin", scope: "platform" }) // "平台超管"
 */
export function roleLabelFromUser(u: { role: string; scope?: string }): string {
  const scope = u.scope ?? "";
  if (scope.startsWith("provider:")) return roleLabel(u.role, "provider");
  if (scope === "platform" || u.role === "superadmin" || u.role === "ops") {
    return roleLabel(u.role, "platform");
  }
  return roleLabel(u.role, "tenant");
}
