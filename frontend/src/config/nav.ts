// 1:1 还原 ui/*.html sidebar 分组与图标
// Note: agent nav and admin nav are scope-dependent (see getNavSections).
// project_manager shares the same nav regardless of scope.
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

// NAV_CONFIG allows UserRole keys plus legacy backward-compat key ("workorder")
const NAV_CONFIG: Partial<Record<UserRole | "workorder", NavSection[]>> = {
  // ── 物业管理员（admin.html）— scope=tenant:{id} ──────────
  admin: [
    {
      title: "工作台",
      items: [
        { label: "项目管理", path: "/admin/projects", icon: "FolderKanban" },
        { label: "数据看板", path: "/admin/dashboard", icon: "LayoutDashboard" },
      ],
    },
    {
      title: "案件管理",
      items: [
        { label: "案件列表", path: "/admin/cases", icon: "List" },
        { label: "案件看板", path: "/admin/cases/kanban", icon: "Kanban" },
        { label: "公海管理", path: "/admin/pool", icon: "Inbox" },
        { label: "业主名单导入", path: "/admin/cases/import", icon: "Upload" },
      ],
    },
    {
      title: "人员管理",
      items: [
        { label: "用户管理", path: "/admin/users", icon: "Users" },
        { label: "坐席设备", path: "/admin/agent-devices", icon: "Smartphone" },
        { label: "服务商合作", path: "/admin/providers", icon: "Briefcase" },
      ],
    },
    {
      title: "结算与报表",
      items: [
        { label: "结算管理", path: "/admin/settlements", icon: "Receipt" },
        // v0.5.4 — 减免大额审批从「法务管理」移入此处（减免是金额谈判，非法务事项）
        { label: "减免大额审批", path: "/admin/discount-approvals", icon: "BadgePercent" },
        // v0.5.9 — 通话计费 + 存证消费(物业方的两项 SaaS 消费视图)
        { label: "通话计费", path: "/admin/billing/minute-usage", icon: "Phone" },
        { label: "存证消费", path: "/admin/billing/blockchain", icon: "Shield" },
        { label: "数据报表", path: "/admin/reports", icon: "BarChart2" },
        { label: "合规月报", path: "/admin/compliance", icon: "Shield" },
      ],
    },
    {
      title: "话术与风控",
      items: [
        { label: "话术库管理", path: "/admin/scripts", icon: "MessageSquare" },
        { label: "话术效果", path: "/admin/scripts/effectiveness", icon: "BarChart3" },
        { label: "风控关键词", path: "/admin/risk-keywords", icon: "ShieldAlert" },
      ],
    },
    {
      title: "法务管理",
      items: [
        { label: "法务转化", path: "/admin/legal-conversion", icon: "Scale" },
        // v1.6.8 — 法务转化两步审批 inbox（催收员申请 → admin 也可代督导审批）
        { label: "法务转化审批", path: "/admin/legal-conversion-approvals", icon: "ClipboardList" },
        // v1.9.0 — 法务内部处理配套：合作律所 + 律师函模板（物业法务起草律师函时选用）
        { label: "合作律所", path: "/admin/partner-law-firms", icon: "Building2" },
        { label: "律师函模板", path: "/admin/internal-letter-templates", icon: "FileText" },
      ],
    },
    {
      title: "系统",
      items: [
        { label: "审计日志", path: "/admin/audit-logs", icon: "ScrollText" },
        { label: "系统配置", path: "/admin/settings", icon: "Settings" },
      ],
    },
  ],

  // ── 督导（mock 9 项 + v1.5.7 新增 5 项）─────────────────
  supervisor: [
    {
      title: "实时监控",
      items: [
        { label: "督导工作台", path: "/supervisor/workspace", icon: "LayoutDashboard" },
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
        { label: "团队监控", path: "/supervisor/team-performance", icon: "Activity" },
        { label: "坐席设备", path: "/admin/agent-devices", icon: "Smartphone" },
      ],
    },
    {
      title: "案件管理",
      items: [
        { label: "案件分配", path: "/supervisor/cases", icon: "ClipboardList" },
        { label: "升级案件处理", path: "/supervisor/escalated", icon: "AlertCircle" },
        { label: "承诺催付", path: "/supervisor/promises", icon: "CalendarClock" },
        { label: "案件超期报警", path: "/supervisor/case-alerts", icon: "BellRing" },
        { label: "减免审批", path: "/supervisor/discount-approvals", icon: "BadgePercent" },
        // v1.6.8 — 法务转化两步审批：催收员申请 → 督导/admin 审批
        { label: "法务转化审批", path: "/supervisor/legal-conversion-approvals", icon: "Scale" },
      ],
    },
    {
      title: "质检与培训",
      items: [
        { label: "质检复核", path: "/supervisor/reviews", icon: "ShieldCheck" },
        { label: "话术反馈", path: "/supervisor/script-labels", icon: "MessageCircle" },
        { label: "风控事件", path: "/supervisor/risk-events", icon: "AlertTriangle" },
        { label: "培训案例库", path: "/supervisor/training", icon: "BookMarked" },
      ],
    },
    {
      title: "我的工作",
      items: [
        { label: "我的 KPI", path: "/supervisor/my-kpi", icon: "BarChart3" },
        { label: "值班排班", path: "/supervisor/shifts", icon: "Calendar" },
        { label: "团队报表", path: "/supervisor/stats", icon: "BarChart2" },
      ],
    },
  ],

  // ── 催收员（agent-pc.html）─────────────────────────────
  // Internal/external work_mode distinction handled at runtime via work_mode field.
  // Internal agents get full workstation; external agents primarily use the App.
  // Scope-based nav selection is done in getNavSections.
  agent: [
    {
      items: [
        { label: "工作台", path: "/agent/workstation", icon: "Headphones" },
        { label: "我的案件", path: "/agent/cases", icon: "ClipboardList" },
        { label: "通话记录", path: "/agent/call-history", icon: "PhoneCall" },
        // v0.6.0 — 提醒中心:即将到期承诺 / 法务申请进度 / 案件 SLA 告警
        { label: "提醒中心", path: "/agent/reminders", icon: "Bell" },
        { label: "个人信息", path: "/agent/profile", icon: "User" },
      ],
    },
  ],

  // ── 法务（legal.html）──────────────────────────────────
  // v1.5.7：物业租户内法务对接人 + 律所/律师都用 legal 角色，按租户/律所上下文区分
  legal: [
    {
      title: "我的工作",
      items: [
        // v0.5.4 — 督导/admin 批准的转法务申请,法务接单选服务包后建 Order
        { label: "待法务接单", path: "/legal/pending-finalize", icon: "Briefcase" },
        // v1.9.0 — 物业法务内部处理新工作台（建单后的 LegalConversionOrder）
        { label: "待内部处理", path: "/legal/internal-orders", icon: "Gavel" },
        // v1.9.1 — 升级律所追踪：status=escalated_to_lawfirm 的订单，可加跟进记录（方案 C 之前先只读派单状态）
        { label: "升级律所追踪", path: "/legal/internal-orders?tab=escalated", icon: "ExternalLink" },
      ],
    },
  ],

  // ── 协调员（v1.5.6 重命名 workorder → coordinator；保留 workorder 兼容旧账号）─
  workorder: [
    {
      items: [
        { label: "工单列表", path: "/workorder/orders", icon: "ClipboardList" },
      ],
    },
  ],
  coordinator: [
    {
      items: [
        { label: "工单列表", path: "/workorder/orders", icon: "ClipboardList" },
      ],
    },
  ],

  // ── 项目经理（物业 / 服务商，project-manager.html）─────
  // Both property-side and provider-side project_managers share this key.
  // Property-side (scope=tenant:{id}) has live-wall access; provider-side does not.
  // Scope-based filtering is done in getNavSections.
  project_manager: [
    {
      items: [
        { label: "项目总览", path: "/pm/dashboard", icon: "LayoutDashboard" },
        // live-wall is only shown for property-side PMs (scope=tenant:*) — see getNavSections
        { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
      ],
    },
  ],

  // ── 平台运营（platform-ops.html）──────────────────────
  ops: [
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
        { label: "服务包目录", path: "/ops/legal-packages", icon: "Package" },
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
  superadmin: [
    {
      title: "运营",
      items: [
        { label: "租户管理", path: "/ops/tenants", icon: "Building2" },
        { label: "服务商管理", path: "/ops/providers", icon: "Briefcase" },
        { label: "结算总览", path: "/ops/settlements", icon: "Receipt" },
        { label: "律所池", path: "/ops/law-firms", icon: "Building2" },
        { label: "服务包目录", path: "/ops/legal-packages", icon: "Package" },
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
        { label: "短信配置", path: "/super/sms-config", icon: "MessageSquare" },
      ],
    },
  ],
};

// Provider-side admin nav (scope = provider:{id}):
// admin role with provider scope gets the provider dashboard menu
// v0.5.6 — 加「案件管理」段(本服务商接手项目下的案件 + 公海 + 看板)
const PROVIDER_ADMIN_NAV: NavSection[] = [
  {
    title: "工作台",
    items: [
      { label: "总览", path: "/provider/dashboard", icon: "LayoutDashboard" },
      { label: "我的项目", path: "/provider/projects", icon: "FolderKanban" },
      { label: "合作物业", path: "/provider/tenants", icon: "Building2" },
    ],
  },
  {
    title: "案件管理",
    items: [
      { label: "案件列表", path: "/provider/cases", icon: "List" },
      { label: "案件看板", path: "/provider/cases/kanban", icon: "KanbanSquare" },
      { label: "服务商公海", path: "/provider/pool", icon: "Inbox" },
    ],
  },
  {
    title: "人员与话术",
    items: [
      { label: "团队管理", path: "/provider/team", icon: "Users" },
      { label: "团队绩效", path: "/provider/team-performance", icon: "TrendingUp" },
      { label: "话术库", path: "/provider/scripts", icon: "MessageSquare" },
    ],
  },
  {
    title: "结算与报表",
    items: [
      { label: "收入结算", path: "/provider/settlements", icon: "Receipt" },
      // v0.5.9 — 跨租户分钟消费(我接的每个租户贡献多少分钟 / 金额)
      { label: "分钟消费", path: "/provider/billing/minute-usage", icon: "Phone" },
      { label: "历史报表", path: "/provider/historical-reports", icon: "Archive" },
    ],
  },
];

// Project manager nav for provider-side (no live-wall access)
const PM_PROVIDER_NAV: NavSection[] = [
  {
    items: [
      { label: "项目总览", path: "/pm/dashboard", icon: "LayoutDashboard" },
    ],
  },
];

// §9.1 — 服务商法务 nav（scope=provider:{id}）
const LEGAL_PROVIDER_NAV: NavSection[] = [
  {
    title: "我的工作",
    items: [
      { label: "法务案件", path: "/provider/legal/cases", icon: "Scale" },
      { label: "转化请求", path: "/provider/legal/requests", icon: "ClipboardList" },
    ],
  },
];

// 服务商督导 nav（scope=provider:{id}）— Phase 1 九项
const SUPERVISOR_PROVIDER_NAV: NavSection[] = [
  {
    title: "实时监控",
    items: [
      { label: "督导工作台", path: "/supervisor/workspace", icon: "LayoutDashboard" },
      { label: "实时通话墙", path: "/supervisor/live-wall", icon: "RadioTower" },
      { label: "团队监控", path: "/supervisor/team-performance", icon: "Activity" },
    ],
  },
  {
    title: "案件管理",
    items: [
      { label: "案件分配", path: "/supervisor/cases", icon: "ClipboardList" },
    ],
  },
  {
    title: "质检与培训",
    items: [
      { label: "质检复核", path: "/supervisor/reviews", icon: "ShieldCheck" },
      { label: "话术反馈", path: "/supervisor/script-labels", icon: "MessageCircle" },
      { label: "风控事件", path: "/supervisor/risk-events", icon: "AlertTriangle" },
    ],
  },
  {
    title: "我的工作",
    items: [
      { label: "我的 KPI", path: "/supervisor/my-kpi", icon: "BarChart3" },
      { label: "值班排班", path: "/supervisor/shifts", icon: "Calendar" },
      { label: "团队报表", path: "/supervisor/stats", icon: "BarChart2" },
    ],
  },
];

// 「下载 App」对所有角色都展示（modal 关掉后还能找到）
export const HELP_SECTION: NavSection = {
  title: "帮助",
  items: [{ label: "下载 App", path: "/help/app", icon: "Smartphone" }],
};

/**
 * Returns sidebar nav sections for a given role and scope.
 * - admin role: scope=provider:{id} → provider dashboard nav; otherwise property admin nav
 * - project_manager: scope=provider:{id} → provider PM nav (no live-wall); otherwise property PM nav
 * - agent: always the agent nav (work_mode internal/external is not used for menu gating)
 * @param role - the user's role string
 * @param scope - the user's scope string (e.g. "tenant:1", "provider:2", "platform")
 */
export function getNavSections(role: UserRole | string, scope?: string): NavSection[] {
  const s = scope ?? "";

  // admin: provider-side vs property-side is scope-driven
  if (role === "admin") {
    const base = s.startsWith("provider:") ? PROVIDER_ADMIN_NAV : (NAV_CONFIG.admin ?? [{ items: [{ label: "控制台", path: "/" }] }]);
    return [...base, HELP_SECTION];
  }

  // project_manager: provider-side loses live-wall
  if (role === "project_manager") {
    const base = s.startsWith("provider:") ? PM_PROVIDER_NAV : (NAV_CONFIG.project_manager ?? [{ items: [{ label: "控制台", path: "/" }] }]);
    return [...base, HELP_SECTION];
  }

  // legal: provider-side gets provider legal nav; property-side gets property legal nav
  if (role === "legal" && s.startsWith("provider:")) {
    return [...LEGAL_PROVIDER_NAV, HELP_SECTION];
  }

  // supervisor: provider-side uses Phase 1 nine-item nav (backend /supervisor/* endpoints are now scope-aware)
  if (role === "supervisor" && s.startsWith("provider:")) {
    return [...SUPERVISOR_PROVIDER_NAV, HELP_SECTION];
  }

  const base =
    NAV_CONFIG[role as UserRole] ?? [{ items: [{ label: "控制台", path: "/" }] }];
  return [...base, HELP_SECTION];
}
