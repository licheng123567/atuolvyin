// Shared TypeScript types across the app.
// Role-specific types live in src/pages/<role>/types.ts
// API response types are generated from OpenAPI schema via src/lib/api-types.ts (Stage E)

export type UserRole =
  | "platform_superadmin"
  | "platform_ops"
  | "provider_admin"
  | "admin"
  | "supervisor"
  | "agent_internal"
  | "agent_external"
  | "legal"
  | "workorder"
  | "project_manager_property"
  | "project_manager_provider"

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
