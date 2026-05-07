// 服务商团队管理 — 1:1 ds-* 风格 + 新建成员
import {
  useCreate,
  useCustomMutation,
  useGetIdentity,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import type { AuthUser } from "../../../providers/auth-provider";
import { formatDate } from "../helpers";

interface TeamMember {
  user_id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface ProviderTenant {
  tenant_id: number;
  tenant_name: string;
}

const ROLE_LABELS: Record<string, string> = {
  provider_admin: "服务商管理员",
  legal: "法务专员",
  workorder: "工单处理员",
  agent_internal: "内部催收员",
  agent_external: "兼职催收员",
  supervisor: "通话质量督导",
  project_manager_provider: "项目负责人（服务商）",
};

const CREATABLE_ROLES = [
  { value: "agent_internal", label: "内部催收员" },
  { value: "agent_external", label: "兼职催收员" },
  { value: "supervisor", label: "通话质量督导" },
];

const ROLE_BADGE_CLASS: Record<string, string> = {
  provider_admin: "ds-badge ds-badge-purple",
  supervisor: "ds-badge ds-badge-blue",
  agent_internal: "ds-badge ds-badge-green",
  agent_external: "ds-badge ds-badge-orange",
};

export function ProviderTeamPage() {
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const PAGE_SIZE = 20;
  const invalidate = useInvalidate();
  const { data: me } = useGetIdentity<AuthUser>();
  const myUserId = me?.id ?? null;

  const { query } = useList<TeamMember>({
    resource: "provider/team",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: TeamMember[] =
    (rawData as unknown as PaginatedResponse<TeamMember>)?.items ??
    (rawData as TeamMember[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isLoading = query.isLoading;

  const { mutate: runAction, mutation } = useCustomMutation();
  const actionLoading = mutation.isPending;

  function handleToggle(member: TeamMember) {
    runAction(
      {
        url: `provider/team/${member.user_id}/active`,
        method: "patch",
        values: { is_active: !member.is_active },
      },
      {
        onSuccess: () => {
          void invalidate({
            resource: "provider/team",
            invalidates: ["list"],
          });
        },
        onError: () => {
          alert("操作失败，请稍后重试");
        },
      },
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">团队管理</h1>
          <div className="page-subtitle">共 {total} 人</div>
        </div>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          onClick={() => setCreateOpen(true)}
        >
          <Plus className="w-3.5 h-3.5" />
          新建团队成员
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>姓名</th>
              <th>手机号</th>
              <th>角色</th>
              <th>加入时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无团队成员
                </td>
              </tr>
            )}
            {items.map((m) => {
              const isSelf = myUserId !== null && m.user_id === myUserId;
              return (
                <tr key={m.user_id}>
                  <td>
                    <strong>{m.name}</strong>
                    {isSelf && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: "var(--color-neutral-400)" }}>
                        （我）
                      </span>
                    )}
                  </td>
                  <td>{m.phone_masked}</td>
                  <td>
                    <span className={ROLE_BADGE_CLASS[m.role] ?? "ds-badge ds-badge-gray"}>
                      {ROLE_LABELS[m.role] ?? m.role}
                    </span>
                  </td>
                  <td>{formatDate(m.created_at)}</td>
                  <td>
                    <span className={m.is_active ? "ds-badge ds-badge-green" : "ds-badge ds-badge-red"}>
                      {m.is_active ? "正常" : "停用"}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      style={{ color: m.is_active ? "#e02424" : "#057a55" }}
                      onClick={() => handleToggle(m)}
                      disabled={isSelf || actionLoading}
                      title={isSelf ? "不能停用自己" : ""}
                    >
                      {m.is_active ? "停用" : "启用"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {totalPages > 1 && (
          <div className="ds-pagination">
            <span className="pagination-info">
              共 {total} 条，第 {page}/{totalPages} 页
            </span>
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((p) => p - 1)}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div className="page-btn" onClick={() => setPage((p) => p + 1)}>
                  ›
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {createOpen && (
        <CreateMemberModal
          onClose={() => setCreateOpen(false)}
          onSuccess={() => {
            setCreateOpen(false);
            query.refetch();
          }}
        />
      )}
    </div>
  );
}

interface CreateMemberModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

function CreateMemberModal({ onClose, onSuccess }: CreateMemberModalProps) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("Demo@123!");
  const [role, setRole] = useState("agent_external");
  const [tenantId, setTenantId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);

  const { query: tenantQuery } = useList<ProviderTenant>({
    resource: "provider/tenants",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const tenantsRaw = tenantQuery.data?.data;
  const tenants: ProviderTenant[] =
    (tenantsRaw as unknown as PaginatedResponse<ProviderTenant>)?.items ??
    (tenantsRaw as ProviderTenant[] | undefined) ??
    [];

  const { mutate: create, mutation } = useCreate();

  function submit() {
    setError(null);
    if (!name.trim() || !/^1[3-9]\d{9}$/.test(phone)) {
      setError("姓名 / 手机号格式不正确");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位");
      return;
    }
    if (tenantId === "") {
      setError("请选择关联租户");
      return;
    }
    create(
      {
        resource: "provider/team",
        values: {
          name: name.trim(),
          phone,
          password,
          role,
          tenant_id: tenantId,
        },
      },
      {
        onSuccess: () => onSuccess(),
        onError: (e) => {
          const detail =
            (e as { response?: { data?: { detail?: { message?: string } } } })
              ?.response?.data?.detail?.message ?? "创建失败";
          setError(detail);
        },
      },
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">新建团队成员</span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          <div className="two-col">
            <div className="form-group">
              <label className="form-label">
                姓名<span className="req">*</span>
              </label>
              <input
                className="form-control"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="请输入姓名"
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                手机号<span className="req">*</span>
              </label>
              <input
                className="form-control"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="11 位手机号"
              />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">
              初始密码<span className="req">*</span>
            </label>
            <input
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8 位以上"
            />
            <div className="form-hint">员工首次登录后可自行修改</div>
          </div>
          <div className="two-col">
            <div className="form-group">
              <label className="form-label">
                角色<span className="req">*</span>
              </label>
              <select
                className="form-control"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {CREATABLE_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">
                关联租户<span className="req">*</span>
              </label>
              <select
                className="form-control"
                value={tenantId}
                onChange={(e) =>
                  setTenantId(e.target.value === "" ? "" : Number(e.target.value))
                }
              >
                <option value="">— 选择合作租户 —</option>
                {tenants.map((t) => (
                  <option key={t.tenant_id} value={t.tenant_id}>
                    {t.tenant_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {error && (
            <div
              style={{
                background: "var(--color-danger-light)",
                color: "var(--color-danger)",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="ds-btn ds-btn-secondary"
            onClick={onClose}
          >
            取消
          </button>
          <button
            type="button"
            className="ds-btn ds-btn-primary"
            onClick={submit}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "创建中…" : "创建成员"}
          </button>
        </div>
      </div>
    </div>
  );
}
