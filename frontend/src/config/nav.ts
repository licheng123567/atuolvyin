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
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "试用跟进", path: "/ops/tenants/trial", icon: "Clock" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "系统公告", path: "/ops/announcements", icon: "Megaphone" },
      ],
    },
    {
      title: "系统管理",
      items: [
        { label: "系统健康", path: "/super/health", icon: "Activity" },
        { label: "审计日志", path: "/super/audit", icon: "FileText" },
        { label: "成本看板", path: "/super/cost", icon: "TrendingUp" },
        { label: "套餐配置", path: "/super/plans", icon: "Package" },
        { label: "LLM Prompts", path: "/super/llm-prompts", icon: "Brain" },
        { label: "区块链配置", path: "/super/blockchain-config", icon: "Link2" },
      ],
    },
  ],
  platform_super: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "试用跟进", path: "/ops/tenants/trial", icon: "Clock" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "系统公告", path: "/ops/announcements", icon: "Megaphone" },
      ],
    },
    {
      title: "系统管理",
      items: [
        { label: "系统健康", path: "/super/health", icon: "Activity" },
        { label: "审计日志", path: "/super/audit", icon: "FileText" },
        { label: "成本看板", path: "/super/cost", icon: "TrendingUp" },
        { label: "套餐配置", path: "/super/plans", icon: "Package" },
        { label: "LLM Prompts", path: "/super/llm-prompts", icon: "Brain" },
        { label: "区块链配置", path: "/super/blockchain-config", icon: "Link2" },
      ],
    },
  ],
  platform_ops: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "试用跟进", path: "/ops/tenants/trial", icon: "Clock" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "系统公告", path: "/ops/announcements", icon: "Megaphone" },
        { label: "客户跟进", path: "/ops/customer-followups", icon: "MessageCircle" },
        { label: "我的操作", path: "/ops/audit-logs", icon: "History" },
      ],
    },
  ],
  admin: [
    {
      items: [
        { label: "管理看板", path: "/admin/dashboard", icon: "LayoutDashboard" },
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
        { label: "用户管理", path: "/admin/users", icon: "Users" },
        { label: "案件管理", path: "/admin/cases", icon: "Briefcase" },
        { label: "案件看板", path: "/admin/cases/kanban", icon: "KanbanSquare" },
        { label: "公海管理", path: "/admin/pool", icon: "Globe" },
        { label: "结算管理", path: "/admin/settlements", icon: "Receipt" },
        { label: "服务商合作", path: "/admin/providers", icon: "Building2" },
        { label: "话术效果", path: "/admin/scripts/effectiveness", icon: "BarChart3" },
        { label: "数据报表", path: "/admin/reports", icon: "TrendingUp" },
        { label: "合规月报", path: "/admin/compliance", icon: "FileText" },
        { label: "法务转化", path: "/admin/legal-conversion", icon: "Scale" },
        { label: "系统配置", path: "/admin/settings", icon: "Settings" },
        { label: "导入案件", path: "/admin/cases/import", icon: "Upload" },
      ],
    },
  ],
  supervisor: [
    {
      items: [
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
        { label: "质检复核", path: "/supervisor/reviews", icon: "ClipboardCheck" },
        { label: "风险警报", path: "/supervisor/alerts", icon: "Bell" },
        { label: "风控时间线", path: "/supervisor/risk-events", icon: "AlertTriangle" },
        { label: "团队绩效", path: "/supervisor/team-performance", icon: "TrendingUp" },
        { label: "话术标注", path: "/supervisor/script-labels", icon: "Tag" },
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
    {
      items: [
        { label: "法务案件", path: "/legal/cases", icon: "Scale" },
      ],
    },
  ],
  workorder: [
    {
      items: [
        { label: "工单管理", path: "/workorder/orders", icon: "ClipboardList" },
      ],
    },
  ],
  project_manager_property: [
    {
      items: [
        { label: "项目看板", path: "/pm/dashboard", icon: "LayoutDashboard" },
      ],
    },
  ],
  project_manager_provider: [
    {
      items: [
        { label: "项目看板", path: "/pm/dashboard", icon: "LayoutDashboard" },
      ],
    },
  ],
  provider_admin: [
    {
      items: [
        { label: "总览", path: "/provider/dashboard", icon: "LayoutDashboard" },
        { label: "合作租户", path: "/provider/tenants", icon: "Building2" },
        { label: "团队管理", path: "/provider/team", icon: "Users" },
        { label: "团队绩效", path: "/provider/team-performance", icon: "TrendingUp" },
        { label: "收入结算", path: "/provider/settlements", icon: "Receipt" },
      ],
    },
  ],
};

// Sprint 14.3 — 「下载 App」对所有角色都展示（modal 关掉后还能找到）
const HELP_SECTION: NavSection = {
  title: "帮助",
  items: [{ label: "下载 App", path: "/help/app", icon: "Smartphone" }],
};

export function getNavSections(role: UserRole | string): NavSection[] {
  const base =
    NAV_CONFIG[role as UserRole] ?? [{ items: [{ label: "控制台", path: "/" }] }];
  return [...base, HELP_SECTION];
}
