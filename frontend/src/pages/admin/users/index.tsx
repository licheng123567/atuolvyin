// v1.5.6 收尾 — 物业用户管理：仅展示物业内部员工，外勤归服务商管理
// v1.6.5 — 服务端分页 + debounce 搜索（不再 frontend filter）
import { useCustom, useCustomMutation, useGo } from "@refinedev/core";
import { Plus } from "lucide-react";
import { useState } from "react";
import { InviteQrModal } from "../../../components/admin/InviteQrModal";
import { PaginationBar } from "../../../components/ui/PaginationBar";
import { SearchInput } from "../../../components/ui/SearchInput";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";

const PAGE_SIZE = 20;

interface UserListResp {
  items: UserItem[];
  total: number;
  page: number;
  page_size: number;
}

interface UserItem {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  created_at: string;
  login_method?: string | null;
  last_login_at?: string | null;
  // v1.5.6 — 多 membership 兼岗
  all_roles?: string[];
}

interface IssueOtpResponse {
  phone_masked: string;
  phone_full: string | null;
  otp: string | null;
}

const ROLE_BADGE_CLASS: Record<string, string> = {
  admin: "ds-badge ds-badge-purple",
  supervisor: "ds-badge ds-badge-orange",
  agent_internal: "ds-badge ds-badge-blue",
  agent_external: "ds-badge ds-badge-blue",
  legal: "ds-badge ds-badge-purple",
  workorder: "ds-badge ds-badge-gray",
  coordinator: "ds-badge ds-badge-gray",
  project_manager_property: "ds-badge ds-badge-purple",
  project_manager_provider: "ds-badge ds-badge-purple",
  provider_admin: "ds-badge ds-badge-purple",
};

const ROLE_LABEL: Record<string, string> = {
  admin: "管理员",
  supervisor: "督导",
  agent_internal: "催收员",
  agent_external: "兼职坐席",
  legal: "法务对接人",
  workorder: "协调员",
  coordinator: "协调员",
  project_manager_property: "项目经理",
  project_manager_provider: "项目经理",
  provider_admin: "服务商管理员",
};

export function UserListPage() {
  const go = useGo();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [invite, setInvite] = useState<{ name: string; resp: IssueOtpResponse } | null>(null);
  const { mutate: issueOtp, mutation: otpMutation } = useCustomMutation();

  const handleIssueOtp = (u: UserItem) => {
    issueOtp(
      { url: `admin/users/${u.id}/issue-otp`, method: "post", values: {} },
      {
        onSuccess: (resp) => {
          setInvite({ name: u.name, resp: resp.data as unknown as IssueOtpResponse });
        },
        onError: () => alert("生成首登码失败，请稍后重试"),
      },
    );
  };

  // v1.6.5 — 服务端分页；搜索通过 q 走后端 ilike，role filter 仍在前端
  const queryParams: Record<string, string | number> = {
    page,
    page_size: PAGE_SIZE,
  };
  if (debouncedQ.trim()) queryParams.q = debouncedQ.trim();

  const { query } = useCustom<UserListResp>({
    url: "admin/users",
    method: "get",
    config: { query: queryParams },
  });

  const data = query.data?.data;
  const allItems = data?.items ?? [];
  const total = data?.total ?? 0;
  const isLoading = query.isLoading;

  // v1.5.6 — 移除外勤 tab：物业 admin 只看内部员工
  const internal = allItems.filter((u) => u.role !== "agent_external");
  const visible = roleFilter
    ? internal.filter((u) => u.role === roleFilter)
    : internal;

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">用户管理</h1>
          <div className="page-subtitle">
            物业内部员工 共 {total} 人
            <span style={{ marginLeft: 12, color: "#9ca3af", fontSize: 12 }}>
              · 外勤由对应服务商在自家系统管理
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
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

      {/* Table */}
      <div className="table-wrap">
        <div className="table-toolbar">
          <SearchInput
            value={q}
            onChange={(v) => { setQ(v); setPage(1); }}
            placeholder="搜索姓名"
            width={220}
          />
          <select
            className="form-control"
            style={{ width: 130 }}
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="">全部角色</option>
            <option value="supervisor">督导</option>
            <option value="agent_internal">内部催收员</option>
            <option value="coordinator">协调员</option>
            <option value="legal">法务对接人</option>
            <option value="project_manager_property">项目经理</option>
            <option value="admin">管理员</option>
          </select>
        </div>

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
                    {u.all_roles && u.all_roles.length > 1 && (
                      <span
                        className="ds-badge ds-badge-purple"
                        style={{ marginLeft: 6, fontSize: 10 }}
                        title={u.all_roles.map((r) => ROLE_LABEL[r] ?? r).join(" / ")}
                      >
                        兼 {u.all_roles.length} 职
                      </span>
                    )}
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
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => go({ to: `/admin/users/${u.id}/edit` })}
                    >
                      编辑
                    </button>
                    {u.login_method === "otp" && !u.last_login_at && (
                      <button
                        type="button"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        disabled={otpMutation.isPending}
                        onClick={() => handleIssueOtp(u)}
                      >
                        重发首登码
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        <PaginationBar
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </div>

      <InviteQrModal
        open={!!invite}
        onClose={() => setInvite(null)}
        userName={invite?.name ?? ""}
        phoneFull={invite?.resp.phone_full ?? null}
        phoneMasked={invite?.resp.phone_masked ?? ""}
        otp={invite?.resp.otp ?? null}
        devMode={!!invite?.resp.otp}
      />
    </div>
  );
}
