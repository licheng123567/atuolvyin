// 1:1 还原 ui/*.html sidebar 分组与图标
import type { UserRole } from "../types";

export interface NavItem {
  label: string;
  path: string;
  icon?: string; // lucide icon name — resolved in Sidebar
  badge?: string; // 'P1' / 数字徽章
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

const NAV_CONFIG: Partial<Record<UserRole, NavSection[]>> = {
  // ── 物业管理员（admin.html）─────────────────────────────
  admin: [
    {
      title: "工作台",
      items: [
        { label: "项目管理", path: "/admin/projects", icon: "FolderKanban" },
        { label: "数据看板", path: "/admin/dashboard", icon: "LayoutDashboard" },
      ],
    },
    {
      title: "CRM",
      items: [
        { label: "案件列表", path: "/admin/cases", icon: "List" },
        { label: "案件看板", path: "/admin/cases/kanban", icon: "Kanban" },
        { label: "公海管理", path: "/admin/pool", icon: "Inbox" },
      ],
    },
    {
      title: "数据管理",
      items: [
        { label: "业主名单导入", path: "/admin/cases/import", icon: "Upload" },
      ],
    },
    {
      title: "人员管理",
      items: [
        { label: "用户管理", path: "/admin/users", icon: "Users" },
        { label: "服务商合作", path: "/admin/providers", icon: "Briefcase" },
      ],
    },
    {
      title: "结算与配置",
      items: [
        { label: "结算管理", path: "/admin/settlements", icon: "Receipt" },
        { label: "话术库管理", path: "/admin/scripts/list", icon: "MessageSquare" },
        { label: "话术效果", path: "/admin/scripts/effectiveness", icon: "BarChart3" },
        {
          label: "数据报表",
          path: "/admin/reports",
          icon: "BarChart2",
          badge: "P1",
        },
        {
          label: "合规月报",
          path: "/admin/compliance",
          icon: "Shield",
          badge: "P1",
        },
        { label: "法务转化", path: "/admin/legal-conversion", icon: "Scale" },
        { label: "系统配置", path: "/admin/settings", icon: "Settings" },
      ],
    },
  ],

  // ── 督导（supervisor.html）─────────────────────────────
  supervisor: [
    {
      items: [
        { label: "我的项目", path: "/supervisor/projects", icon: "FolderKanban" },
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
        {
          label: "质检复核",
          path: "/supervisor/reviews",
          icon: "ShieldCheck",
        },
        {
          label: "风险警报",
          path: "/supervisor/alerts",
          icon: "Bell",
        },
        {
          label: "风控事件",
          path: "/supervisor/risk-events",
          icon: "AlertTriangle",
        },
        {
          label: "团队报表",
          path: "/supervisor/team-performance",
          icon: "BarChart2",
        },
        {
          label: "话术标注",
          path: "/supervisor/script-labels",
          icon: "MessageCircle",
        },
      ],
    },
  ],

  // ── 内部坐席（agent-pc.html）───────────────────────────
  agent_internal: [
    {
      items: [
        { label: "我的案件", path: "/agent/cases", icon: "ClipboardList" },
      ],
    },
  ],

  // ── 外部兼职坐席（PC 走 Help 引导）─────────────────────
  agent_external: [
    {
      items: [
        { label: "下载 App 拨号", path: "/help/app", icon: "Smartphone" },
      ],
    },
  ],

  // ── 法务（legal.html）──────────────────────────────────
  legal: [
    {
      items: [
        { label: "案件清单", path: "/legal/cases", icon: "List" },
      ],
    },
  ],

  // ── 工单专员（workorder.html）─────────────────────────
  workorder: [
    {
      items: [
        { label: "工单列表", path: "/workorder/orders", icon: "ClipboardList" },
      ],
    },
  ],

  // ── 项目经理（物业 / 服务商，project-manager.html）─────
  project_manager_property: [
    {
      items: [
        { label: "项目总览", path: "/pm/dashboard", icon: "LayoutDashboard" },
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
      ],
    },
  ],
  project_manager_provider: [
    {
      items: [
        { label: "项目总览", path: "/pm/dashboard", icon: "LayoutDashboard" },
      ],
    },
  ],

  // ── 服务商管理员（provider-admin.html）─────────────────
  provider_admin: [
    {
      items: [
        { label: "总览", path: "/provider/dashboard", icon: "LayoutDashboard" },
        { label: "合作租户", path: "/provider/tenants", icon: "Building2" },
        { label: "团队管理", path: "/provider/team", icon: "Users" },
        { label: "团队绩效", path: "/provider/team-performance", icon: "TrendingUp" },
        { label: "话术库", path: "/provider/scripts", icon: "MessageSquare" },
        { label: "收入结算", path: "/provider/settlements", icon: "Receipt" },
      ],
    },
  ],

  // ── 平台运营（platform-ops.html）──────────────────────
  platform_ops: [
    {
      title: "租户管理",
      items: [
        { label: "租户列表", path: "/ops/tenants", icon: "Building2" },
        { label: "试用跟进", path: "/ops/tenants/trial", icon: "Clock" },
        { label: "客户跟进", path: "/ops/customer-followups", icon: "MessageCircle" },
      ],
    },
    {
      title: "服务商",
      items: [
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
      ],
    },
    {
      title: "法务",
      items: [
        { label: "律所池", path: "/ops/law-firms", icon: "Building2" },
        { label: "法务工作台", path: "/ops/legal-workstation", icon: "Scale" },
      ],
    },
    {
      title: "其他",
      items: [
        { label: "系统公告", path: "/ops/announcements", icon: "Megaphone" },
        { label: "我的操作", path: "/ops/audit-logs", icon: "History" },
      ],
    },
  ],

  // ── 平台超管（platform-superadmin.html）────────────────
  platform_superadmin: [
    {
      title: "运营",
      items: [
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "律所池", path: "/ops/law-firms", icon: "Building2" },
        { label: "法务工作台", path: "/ops/legal-workstation", icon: "Scale" },
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
      title: "运营",
      items: [
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "律所池", path: "/ops/law-firms", icon: "Building2" },
        { label: "法务工作台", path: "/ops/legal-workstation", icon: "Scale" },
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
};

// 「下载 App」对所有角色都展示（modal 关掉后还能找到）
// agent_external 已经在主菜单里有，避免重复
const HELP_SECTION: NavSection = {
  title: "帮助",
  items: [{ label: "下载 App", path: "/help/app", icon: "Smartphone" }],
};

export function getNavSections(role: UserRole | string): NavSection[] {
  const base =
    NAV_CONFIG[role as UserRole] ?? [{ items: [{ label: "控制台", path: "/" }] }];
  // agent_external 主菜单已包含 /help/app，不再重复
  if (role === "agent_external") return base;
  return [...base, HELP_SECTION];
}
