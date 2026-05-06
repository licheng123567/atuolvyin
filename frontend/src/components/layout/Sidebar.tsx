import { useGetIdentity, useLogout } from "@refinedev/core";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  Building2,
  ClipboardCheck,
  FileText,
  History,
  Home,
  LayoutDashboard,
  Link2,
  LogOut,
  Megaphone,
  Package,
  Receipt,
  Settings,
  Tag,
  TrendingUp,
  Users,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
import { getNavSections } from "../../config/nav";
import { cn } from "../../lib/utils";

const ROLE_LABELS: Record<string, string> = {
  platform_superadmin: "平台超管",
  platform_super: "平台超管",
  platform_ops: "平台运营员",
  provider_admin: "服务商管理员",
  admin: "物业管理员",
  supervisor: "主管/督导",
  agent_internal: "催收员（内部）",
  agent_external: "催收员（兼职）",
  legal: "法务专员",
  workorder: "工单处理员",
  project_manager_property: "项目负责人（物业）",
  project_manager_provider: "项目负责人（服务商）",
};

const ICON_MAP: Record<string, React.ElementType> = {
  "/": Home,
  "/ops/tenants": Building2,
  "/admin/users": Users,
  "/admin/providers": Building2,
  "/admin/scripts/effectiveness": BarChart3,
  "/admin/reports": TrendingUp,
  "/admin/compliance": FileText,
  "/admin/settings": Settings,
  "/supervisor/reviews": ClipboardCheck,
  "/supervisor/risk-events": AlertTriangle,
  "/supervisor/team-performance": TrendingUp,
  "/supervisor/script-labels": Tag,
  "/ops/settlements": Receipt,
  "/ops/announcements": Megaphone,
  "/ops/audit-logs": History,
  "/super/llm-prompts": Brain,
  "/super/blockchain-config": Link2,
  "/provider/dashboard": LayoutDashboard,
  "/provider/tenants": Building2,
  "/provider/team": Users,
  "/provider/settlements": Receipt,
  "/super/health": Activity,
  "/super/audit": FileText,
  "/super/cost": TrendingUp,
  "/super/plans": Package,
};

export function Sidebar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const { mutate: logout } = useLogout();
  const location = useLocation();

  const initials = user?.name?.slice(0, 1) ?? "?";
  const sections = user ? getNavSections(user.role) : [];

  return (
    <aside
      className="flex flex-col bg-white border-r border-[var(--color-neutral-200)] flex-shrink-0"
      style={{ width: "var(--sidebar-width)" }}
    >
      {/* Logo row */}
      <div
        className="flex items-center px-5 border-b border-[var(--color-neutral-200)] flex-shrink-0"
        style={{ height: "var(--topbar-height)" }}
      >
        <span className="text-base font-bold text-[var(--color-primary)]">
          有证慧催
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {sections.map((section, si) => (
          <div key={si}>
            {section.title && (
              <p className="px-3 mb-1 text-xs font-medium text-[var(--color-neutral-400)] uppercase tracking-wider">
                {section.title}
              </p>
            )}
            {section.items.map((item) => {
              const Icon = ICON_MAP[item.path] ?? Home;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors",
                    isActive
                      ? "bg-[var(--color-primary)] text-white font-medium"
                      : "text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]",
                  )}
                  style={{ borderRadius: "var(--radius-md)" }}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User block + logout */}
      <div className="border-t border-[var(--color-neutral-200)] p-3">
        {user && (
          <div className="flex items-center gap-2 px-2 py-1 mb-1">
            <div
              className="flex-shrink-0 flex items-center justify-center rounded-full text-white text-xs font-semibold"
              style={{ width: 28, height: 28, background: "var(--color-primary)" }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--color-neutral-900)] truncate">
                {user.name}
              </p>
              <p className="text-xs text-[var(--color-neutral-400)] truncate">
                {ROLE_LABELS[user.role] ?? user.role}
              </p>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => logout()}
          className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded transition-colors text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-100)]"
          style={{ borderRadius: "var(--radius-md)" }}
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          退出登录
        </button>
      </div>
    </aside>
  );
}
