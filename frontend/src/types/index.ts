// Shared TypeScript types across the app.
// Role-specific types live in src/pages/<role>/types.ts
// API response types are generated from OpenAPI schema via src/lib/api-types.ts (Stage E)

// New role model (Tasks 1-7 backend refactor):
// - provider_admin → admin (scope = provider:{id})
// - agent_internal / agent_external → agent (internal/external = work_mode field)
// - project_manager_property / project_manager_provider → project_manager
// - platform_superadmin → superadmin
// - platform_ops → ops
// Property-side vs provider-side is now carried by the `scope` field on AuthUser:
//   scope "tenant:{id}" = property side, "provider:{id}" = service-provider side, "platform" = platform

export type OrgRole =
  | "admin"
  | "project_manager"
  | "supervisor"
  | "agent"
  | "legal"
  | "coordinator";

export type PlatformRole = "superadmin" | "ops";

export type UserRole = OrgRole | PlatformRole;

// WorkMode replaces the old agent_internal / agent_external role distinction.
// The login response and /me endpoint expose `work_mode` on the agent's membership.
export type WorkMode = "internal" | "external";

export interface ApiError {
  code: string
  message: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
