import { useCustom, useCustomMutation, useGetIdentity, useLogout } from "@refinedev/core";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut, RefreshCw, Search, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";
import { roleLabelFromMembership, roleLabelFromUser } from "../../lib/roleLabel";
import { NotificationBell } from "../notifications/NotificationBell";
import { AlertNotificationCenter } from "../supervisor/AlertNotificationCenter";

// v0.5.6 — ROLE_LABELS 已迁出到 src/lib/roleLabel.ts(SSOT);本文件改用 roleLabelFromUser
// / roleLabelFromMembership 辅助函数,自动按 scope 区分物业 / 服务商 / 平台。
const SUPERVISOR_ROLES = new Set(["supervisor", "admin", "superadmin"]);

interface MembershipItem {
  membership_id: number;
  tenant_id: number | null;
  tenant_name: string | null;
  provider_id: number | null;
  provider_name: string | null;
  role: string;
  is_current: boolean;
}

const ROLE_BADGE_BG: Record<string, { bg: string; color: string }> = {
  superadmin: { bg: "#fdf2f8", color: "#be185d" },
  ops: { bg: "#f3e8ff", color: "#7e22ce" },
  admin: { bg: "#dbeafe", color: "#1d4ed8" },
  supervisor: { bg: "#cffafe", color: "#0e7490" },
  agent: { bg: "#ecfccb", color: "#3f6212" },
  legal: { bg: "#ddd6fe", color: "#5b21b6" },
  workorder: { bg: "#ffedd5", color: "#9a3412" },
  coordinator: { bg: "#ffedd5", color: "#9a3412" },
  project_manager: { bg: "#e0e7ff", color: "#3730a3" },
};

export function Topbar() {
  const { data: user } = useGetIdentity<AuthUser>();
  const navigate = useNavigate();
  const { mutate: logout } = useLogout();
  const isSupervisor = SUPERVISOR_ROLES.has(user?.role ?? "");
  const roleLabel = user ? roleLabelFromUser(user) : null;
  const roleBadge = user
    ? (ROLE_BADGE_BG[user.role] ?? { bg: "#f3f4f6", color: "#374151" })
    : null;

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // v1.5.6 — 多 membership 切换
  const { query: membershipsQuery } = useCustom<MembershipItem[]>({
    url: "me/memberships",
    method: "get",
    queryOptions: { enabled: !!user },
  });
  const memberships = membershipsQuery.data?.data ?? [];
  const hasMultiple = memberships.length > 1;
  const { mutate: switchMembership, mutation: switchMutation } = useCustomMutation();
  const queryClient = useQueryClient();  // v1.6.9 — 切换身份时清空 React Query 缓存

  const handleSwitch = (membershipId: number) => {
    switchMembership(
      { url: "auth/select-membership", method: "post", values: { membership_id: membershipId, device_type: "pc" } },
      {
        onSuccess: (resp) => {
          const data = resp.data as unknown as {
            access_token: string;
            user_id: number;
            name: string;
            role: string;
            tenant_id: number | null;
            tenant_name: string | null;
            scope: string;
          };
          if (!data?.access_token) {
            // 后端没返回 token —— 不要切换 / 不要刷新（避免身份不一致 → 死循环加载）
            alert("切换角色失败：服务端未返回新令牌，请重新登录");
            return;
          }
          localStorage.setItem("autoluyin_token", data.access_token);
          localStorage.setItem("autoluyin_user", JSON.stringify({
            id: data.user_id,
            name: data.name,
            role: data.role,
            tenant_id: data.tenant_id,
            tenant_name: data.tenant_name,
            scope: data.scope,
          }));
          // v1.6.9 — fix: 清空所有 React Query 缓存，避免新角色复用旧角色的查询结果
          // （多身份用户从督导切到催收员 → 案件详情卡顿在「加载中」就是这个 stale 缓存导致）
          queryClient.clear();
          // 用 replace() 强制硬刷新，且不在 history 留 "/" 旧条目
          window.location.replace("/");
        },
        onError: () => alert("切换角色失败，请稍后重试"),
      },
    );
  };

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

      {/* v1.5.7 — 全局搜索（仅有租户上下文的角色显示）*/}
      {user?.tenant_id && (user.role === "admin" || user.role === "supervisor") && (
        <GlobalSearchBox />
      )}

      <NotificationBell />
      {isSupervisor && <AlertNotificationCenter />}

      {user && (
        <div ref={menuRef} style={{ position: "relative", marginLeft: 12 }}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            title={hasMultiple ? `当前角色：${roleLabel ?? ""}（点击可切换 ${memberships.length} 个角色）` : undefined}
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
            {hasMultiple && (
              <span
                style={{
                  fontSize: 10,
                  padding: "1px 6px",
                  borderRadius: 8,
                  background: "#eff6ff",
                  color: "var(--color-primary)",
                  fontWeight: 600,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 2,
                }}
              >
                <RefreshCw className="w-2.5 h-2.5" /> 可切换 {memberships.length}
              </span>
            )}
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

              {hasMultiple && (
                <>
                  <div style={{ borderTop: "1px solid #e5e7eb" }} />
                  <div style={{ padding: "8px 14px 4px", fontSize: 11, color: "#9ca3af", display: "flex", alignItems: "center", gap: 6 }}>
                    <RefreshCw className="w-3 h-3" />
                    切换角色
                  </div>
                  {memberships.map((m) => (
                    <button
                      key={m.membership_id}
                      type="button"
                      disabled={m.is_current || switchMutation.isPending}
                      onClick={() => handleSwitch(m.membership_id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 14px",
                        fontSize: 12,
                        color: m.is_current ? "var(--color-primary)" : "var(--color-neutral-700)",
                        background: m.is_current ? "#eff6ff" : "transparent",
                        border: "none",
                        width: "100%",
                        cursor: m.is_current ? "default" : "pointer",
                        textAlign: "left",
                        fontWeight: m.is_current ? 600 : 400,
                      }}
                      onMouseEnter={(e) => {
                        if (!m.is_current) e.currentTarget.style.background = "#f9fafb";
                      }}
                      onMouseLeave={(e) => {
                        if (!m.is_current) e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <span>
                        {roleLabelFromMembership(m)}
                        <span style={{ color: "#9ca3af", marginLeft: 6, fontSize: 11 }}>
                          @ {m.provider_name ?? m.tenant_name ?? "平台"}
                        </span>
                      </span>
                      {m.is_current && <span style={{ fontSize: 10, color: "var(--color-primary)" }}>当前</span>}
                    </button>
                  ))}
                </>
              )}

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

function GlobalSearchBox() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");

  function handleSubmit() {
    const k = keyword.trim();
    if (!k) return;
    navigate(`/admin/cases?keyword=${encodeURIComponent(k)}`);
    setKeyword("");
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        background: "#f3f4f6",
        borderRadius: 6,
        marginRight: 8,
        minWidth: 220,
      }}
    >
      <Search className="w-3.5 h-3.5 text-[var(--color-neutral-500)]" />
      <input
        type="text"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSubmit();
        }}
        placeholder="搜索业主姓名 / 房号"
        style={{
          flex: 1,
          background: "transparent",
          border: "none",
          outline: "none",
          fontSize: 13,
          color: "var(--color-neutral-700)",
        }}
      />
    </div>
  );
}
