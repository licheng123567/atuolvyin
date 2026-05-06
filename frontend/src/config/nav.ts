import type { UserRole } from "../types";

export interface NavItem {
  label: string;
  path: string;
  icon?: string; // lucide icon name — resolved in Sidebar
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

const NAV_CONFIG: Partial<Record<UserRole, NavSection[]>> = {
  platform_superadmin: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants" },
      ],
    },
  ],
  platform_ops: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants" },
      ],
    },
  ],
  admin: [
    {
      items: [
        { label: "管理看板", path: "/admin/dashboard", icon: "LayoutDashboard" },
        { label: "用户管理", path: "/admin/users", icon: "Users" },
        { label: "案件管理", path: "/admin/cases", icon: "Briefcase" },
        { label: "案件看板", path: "/admin/cases/kanban", icon: "KanbanSquare" },
        { label: "公海管理", path: "/admin/pool", icon: "Globe" },
        { label: "导入案件", path: "/admin/cases/import", icon: "Upload" },
      ],
    },
  ],
  supervisor: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "案件总览", path: "/supervisor/cases" },
      ],
    },
  ],
  agent_internal: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
  agent_external: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
  legal: [
    { items: [{ label: "控制台", path: "/" }] },
  ],
  workorder: [
    { items: [{ label: "控制台", path: "/" }] },
  ],
  project_manager_property: [
    { items: [{ label: "控制台", path: "/" }] },
  ],
  project_manager_provider: [
    { items: [{ label: "控制台", path: "/" }] },
  ],
  provider_admin: [
    { items: [{ label: "控制台", path: "/" }] },
  ],
};

export function getNavSections(role: UserRole | string): NavSection[] {
  return NAV_CONFIG[role as UserRole] ?? [{ items: [{ label: "控制台", path: "/" }] }];
}
