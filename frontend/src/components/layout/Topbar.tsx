import { useGetIdentity } from "@refinedev/core";
import type { AuthUser } from "../../providers/auth-provider";
import { NotificationBell } from "../notifications/NotificationBell";
import { AlertNotificationCenter } from "../supervisor/AlertNotificationCenter";

const SUPERVISOR_ROLES = new Set(["supervisor", "admin", "platform_super"]);

export function Topbar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const isSupervisor = SUPERVISOR_ROLES.has(user?.role ?? "");

  return (
    <header
      className="flex items-center px-5 bg-white border-b border-[var(--color-neutral-200)] flex-shrink-0"
      style={{
        height: "var(--topbar-height)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Breadcrumb slot — filled by individual pages via React context in Sprint 1 */}
      <div className="flex-1" />

      <NotificationBell />
      {isSupervisor && <AlertNotificationCenter />}

      {user && (
        <span className="text-sm text-[var(--color-neutral-600)] ml-3">
          {user.name}
        </span>
      )}
    </header>
  );
}
