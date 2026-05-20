// 1:1 还原 ui/*.html sidebar：分组标题 + 图标 + P1/数字 badge
import { useGetIdentity, useLogout } from "@refinedev/core";
import * as Icons from "lucide-react";
import { Home, LogOut } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
import { getNavSections } from "../../config/nav";
import { roleLabelFromUser } from "../../lib/roleLabel";

// v0.5.6 — ROLE_LABELS 已迁出到 src/lib/roleLabel.ts(SSOT)

type LucideMap = Record<string, React.ElementType>;
function resolveIcon(name: string | undefined): React.ElementType {
  if (!name) return Home;
  const m = Icons as unknown as LucideMap;
  return m[name] ?? Home;
}

export function Sidebar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const { mutate: logout } = useLogout();
  const location = useLocation();

  const initials = user?.name?.slice(0, 1) ?? "?";
  const sections = user ? getNavSections(user.role, user.scope) : [];

  return (
    <aside
      className="flex flex-col bg-white border-r border-[var(--color-neutral-200)] flex-shrink-0"
      style={{ width: "var(--sidebar-width)" }}
    >
      {/* Logo row — 与原型 topbar-logo 风格一致 */}
      <div
        className="flex items-center px-5 border-b border-[var(--color-neutral-200)] flex-shrink-0"
        style={{ height: "var(--topbar-height)" }}
      >
        <span
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: "var(--color-primary)",
            letterSpacing: "-0.3px",
          }}
        >
          有证慧催
        </span>
      </div>

      {/* Navigation — 用 design-system 的 .sidebar-* class */}
      <nav className="flex-1 overflow-y-auto" style={{ padding: "12px 8px" }}>
        {sections.map((section, si) => (
          <div key={si}>
            {section.title && (
              <div className="sidebar-section-label">{section.title}</div>
            )}
            {section.items.map((item) => {
              const Icon = resolveIcon(item.icon);
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`sidebar-item${isActive ? " active" : ""}`}
                >
                  <Icon />
                  <span style={{ flex: 1, minWidth: 0 }}>{item.label}</span>
                  {item.badge && <NavBadge text={item.badge} />}
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
                {roleLabelFromUser(user)}
              </p>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => logout()}
          className="sidebar-item"
          style={{ width: "100%", color: "var(--color-neutral-600)" }}
        >
          <LogOut />
          退出登录
        </button>
      </div>
    </aside>
  );
}

function NavBadge({ text }: { text: string }) {
  // P1 用灰底，纯数字（>0）用红底（与原型 .sidebar-badge 一致）
  const isP1 = /^P\d+$/.test(text);
  if (isP1) {
    return (
      <span
        className="ds-badge ds-badge-gray"
        style={{
          fontSize: 10,
          padding: "1px 6px",
          marginLeft: "auto",
        }}
      >
        {text}
      </span>
    );
  }
  return <span className="sidebar-badge">{text}</span>;
}
