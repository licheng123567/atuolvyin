import { useGetIdentity, useLogout } from "@refinedev/core";
import { ChevronDown, LogOut, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
import { NotificationBell } from "../notifications/NotificationBell";
import { AlertNotificationCenter } from "../supervisor/AlertNotificationCenter";

const SUPERVISOR_ROLES = new Set(["supervisor", "admin", "platform_super"]);

const ROLE_LABELS: Record<string, string> = {
  platform_superadmin: "平台超管",
  platform_super: "平台超管",
  platform_ops: "平台运营员",
  provider_admin: "服务商管理员",
  admin: "物业管理员",
  supervisor: "主管/督导",
  agent_internal: "催收员",
  agent_external: "催收员",
  legal: "法务专员",
  workorder: "工单处理员",
  project_manager_property: "项目负责人",
  project_manager_provider: "项目负责人",
};

const ROLE_BADGE_BG: Record<string, { bg: string; color: string }> = {
  platform_superadmin: { bg: "#fdf2f8", color: "#be185d" },
  platform_super: { bg: "#fdf2f8", color: "#be185d" },
  platform_ops: { bg: "#f3e8ff", color: "#7e22ce" },
  provider_admin: { bg: "#fef3c7", color: "#b45309" },
  admin: { bg: "#dbeafe", color: "#1d4ed8" },
  supervisor: { bg: "#cffafe", color: "#0e7490" },
  agent_internal: { bg: "#ecfccb", color: "#3f6212" },
  agent_external: { bg: "#ecfccb", color: "#3f6212" },
  legal: { bg: "#ddd6fe", color: "#5b21b6" },
  workorder: { bg: "#ffedd5", color: "#9a3412" },
  project_manager_property: { bg: "#e0e7ff", color: "#3730a3" },
  project_manager_provider: { bg: "#e0e7ff", color: "#3730a3" },
};

export function Topbar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const navigate = useNavigate();
  const { mutate: logout } = useLogout();
  const isSupervisor = SUPERVISOR_ROLES.has(user?.role ?? "");
  const roleLabel = user ? (ROLE_LABELS[user.role] ?? user.role) : null;
  const roleBadge = user
    ? (ROLE_BADGE_BG[user.role] ?? { bg: "#f3f4f6", color: "#374151" })
    : null;

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [menuOpen]);

  return (
    <header
      className="flex items-center px-5 bg-white border-b border-[var(--color-neutral-200)] flex-shrink-0"
      style={{
        height: "var(--topbar-height)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Tenant + role badge — admin.html topbar-tenant + role badge */}
      {user?.tenant_name && (
        <>
          <span
            className="text-sm font-medium text-[var(--color-neutral-700)]"
            style={{ marginRight: 10 }}
          >
            {user.tenant_name}
          </span>
        </>
      )}
      {roleLabel && roleBadge && (
        <span
          style={{
            fontSize: 12,
            padding: "3px 10px",
            borderRadius: 12,
            background: roleBadge.bg,
            color: roleBadge.color,
            fontWeight: 500,
          }}
        >
          {roleLabel}
        </span>
      )}

      <div className="flex-1" />

      <NotificationBell />
      {isSupervisor && <AlertNotificationCenter />}

      {user && (
        <div ref={menuRef} style={{ position: "relative", marginLeft: 12 }}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 13,
              color: "var(--color-neutral-600)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              padding: "4px 8px",
              borderRadius: 6,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f3f4f6")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <span>{user.name}</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {menuOpen && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                right: 0,
                background: "white",
                border: "1px solid var(--color-neutral-200)",
                borderRadius: 8,
                boxShadow: "var(--shadow-md, 0 4px 12px rgba(0,0,0,.1))",
                minWidth: 160,
                zIndex: 100,
                overflow: "hidden",
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  navigate("/me");
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  fontSize: 13,
                  color: "var(--color-neutral-700)",
                  background: "transparent",
                  border: "none",
                  width: "100%",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#f9fafb")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <User className="w-4 h-4" />
                我的账号
              </button>
              <div style={{ borderTop: "1px solid #e5e7eb" }} />
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  fontSize: 13,
                  color: "var(--color-neutral-700)",
                  background: "transparent",
                  border: "none",
                  width: "100%",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#fef2f2")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <LogOut className="w-4 h-4" />
                退出登录
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
