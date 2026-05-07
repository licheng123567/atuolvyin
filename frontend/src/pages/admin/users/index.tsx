// 1:1 还原 ui/admin.html#a-users 用户管理（含内部员工 / 外部兼职 tabs）
import { useGo, useList } from "@refinedev/core";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface UserItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_BADGE_CLASS: Record<string, string> = {
  admin: "ds-badge ds-badge-purple",
  supervisor: "ds-badge ds-badge-orange",
  agent_internal: "ds-badge ds-badge-blue",
  agent_external: "ds-badge ds-badge-blue",
  legal: "ds-badge ds-badge-purple",
  workorder: "ds-badge ds-badge-gray",
  project_manager_property: "ds-badge ds-badge-purple",
  project_manager_provider: "ds-badge ds-badge-purple",
  provider_admin: "ds-badge ds-badge-purple",
};

const ROLE_LABEL: Record<string, string> = {
  admin: "管理员",
  supervisor: "督导",
  agent_internal: "催收员",
  agent_external: "兼职坐席",
  legal: "法务",
  workorder: "工单专员",
  project_manager_property: "项目经理",
  project_manager_provider: "项目经理",
  provider_admin: "服务商管理员",
};

type Tab = "internal" | "external";

export function UserListPage() {
  const go = useGo();
  const [tab, setTab] = useState<Tab>("internal");
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  const { query } = useList<UserItem>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const rawData = query.data?.data;
  const allItems: UserItem[] =
    (rawData as unknown as PaginatedResponse<UserItem>)?.items ??
    (rawData as UserItem[] | undefined) ??
    [];
  const isLoading = query.isLoading;

  const internal = allItems.filter((u) => u.role !== "agent_external");
  const external = allItems.filter((u) => u.role === "agent_external");

  const visible = (tab === "internal" ? internal : external).filter((u) => {
    if (q && !u.name.includes(q) && !u.phone_masked.includes(q)) return false;
    if (roleFilter && u.role !== roleFilter) return false;
    return true;
  });

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">用户管理</h1>
          <div className="page-subtitle">
            内部 {internal.length} · 外部兼职 {external.length}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ds-btn ds-btn-secondary" disabled>
            生成邀请链接
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={() => go({ to: "/admin/users/new" })}
          >
            <Plus className="w-3.5 h-3.5" />
            新建员工
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="ds-tabs">
        <div
          className={`ds-tab${tab === "internal" ? " active" : ""}`}
          onClick={() => setTab("internal")}
        >
          内部员工{" "}
          <span
            className="ds-badge ds-badge-gray"
            style={{ fontSize: 11, marginLeft: 4 }}
          >
            {internal.length}
          </span>
        </div>
        <div
          className={`ds-tab${tab === "external" ? " active" : ""}`}
          onClick={() => setTab("external")}
        >
          外部兼职{" "}
          <span
            className="ds-badge ds-badge-gray"
            style={{ fontSize: 11, marginLeft: 4 }}
          >
            {external.length}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <div className="table-toolbar">
          <div className="search-box">
            <Search className="w-3.5 h-3.5" />
            <input
              type="text"
              className="form-control"
              placeholder="搜索姓名 / 手机"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          {tab === "internal" && (
            <select
              className="form-control"
              style={{ width: 130 }}
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
            >
              <option value="">全部角色</option>
              <option value="supervisor">督导</option>
              <option value="agent_internal">催收员</option>
              <option value="legal">法务</option>
              <option value="workorder">工单专员</option>
              <option value="admin">管理员</option>
            </select>
          )}
        </div>

        {tab === "internal" ? (
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>手机</th>
                <th>角色</th>
                <th>所属主管</th>
                <th>私海数 / 上限</th>
                <th>本月通话</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                    加载中…
                  </td>
                </tr>
              )}
              {!isLoading && visible.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                    无匹配的内部员工
                  </td>
                </tr>
              )}
              {visible.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                    {u.phone_masked}
                  </td>
                  <td>
                    <span
                      className={
                        ROLE_BADGE_CLASS[u.role] ?? "ds-badge ds-badge-gray"
                      }
                    >
                      {ROLE_LABEL[u.role] ?? u.role}
                    </span>
                  </td>
                  <td className="text-muted">—</td>
                  <td className="text-muted">—</td>
                  <td className="text-muted">—</td>
                  <td>
                    <span
                      className={
                        u.is_active
                          ? "ds-badge ds-badge-green"
                          : "ds-badge ds-badge-gray"
                      }
                    >
                      {u.is_active ? "正常" : "停用"}
                    </span>
                  </td>
                  <td>
                    <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm">
                      编辑
                    </button>
                    {u.is_active && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        style={{ color: "#e02424" }}
                      >
                        停用
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table>
            <thead>
              <tr>
                <th>姓名</th>
                <th>手机</th>
                <th>服务商</th>
                <th>配额 / 上限</th>
                <th>有效期</th>
                <th>可拨打时段</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                    暂无外部兼职坐席
                  </td>
                </tr>
              )}
              {visible.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                    {u.phone_masked}
                  </td>
                  <td className="text-muted">—</td>
                  <td className="text-muted">—</td>
                  <td className="text-muted">—</td>
                  <td className="text-muted">—</td>
                  <td>
                    <span
                      className={
                        u.is_active
                          ? "ds-badge ds-badge-green"
                          : "ds-badge ds-badge-gray"
                      }
                    >
                      {u.is_active ? "正常" : "停用"}
                    </span>
                  </td>
                  <td>
                    <button type="button" className="ds-btn ds-btn-ghost ds-btn-sm">
                      编辑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
