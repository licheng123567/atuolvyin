// Shared TypeScript types across the app.
// Role-specific types live in src/pages/<role>/types.ts
// API response types are generated from OpenAPI schema via src/lib/api-types.ts (Stage E)

export type UserRole =
  | "platform_superadmin"
  | "platform_super"
  | "platform_ops"
  | "provider_admin"
  | "admin"
  | "supervisor"
  | "agent_internal"
  | "agent_external"
  | "legal"
  | "workorder"      // v1.5.5 起重命名为 coordinator；保留以兼容旧数据
  | "coordinator"    // v1.5.6 — 物业内部协调员（接服务商工单 + 调度内部各职能）
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
