// 服务商团队管理 — 1:1 ds-* 风格 + 新建成员
// v0.7.0 — 新建成员 modal 改用 RightDrawer + 移除密码字段(OTP 首登,对齐 admin/users/new)
import {
  useCreate,
  useCustomMutation,
  useGetIdentity,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { Loader2, Plus, UserPlus } from "lucide-react";
import { useState } from "react";
import { RightDrawer } from "../../../components/ui/RightDrawer";
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

// v1.0.0 — 删除 ProviderTenant interface(原用于「关联物业」下拉,已弃用)

// v0.5.6 — ROLE_LABELS 已迁出到 src/lib/roleLabel.ts;服务商团队管理 scope=provider
import { roleLabel as roleLabelFn } from "../../../lib/roleLabel";
const ROLE_LABELS = (r: string) => roleLabelFn(r, "provider");

// v0.7.0 — 对齐 admin/users/new.tsx 的角色描述风格(冗长 label 帮助新人理解)
// v1.0.0 — 服务商支持 3 个组织角色(对齐物业 admin 但无 legal,服务商不做法务)
const CREATABLE_ROLES = [
  { value: "agent", label: "催收员(拨打电话 / 跟进案件)" },
  { value: "supervisor", label: "督导(实时质检 + 团队组长)" },
  { value: "project_manager", label: "项目经理(项目运营 + 全员看板)" },
];

const ROLE_BADGE_CLASS: Record<string, string> = {
  admin: "ds-badge ds-badge-purple",
  supervisor: "ds-badge ds-badge-blue",
  agent: "ds-badge ds-badge-green",
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
                      {ROLE_LABELS(m.role)}
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
  const [role, setRole] = useState("agent");
  const [error, setError] = useState<string | null>(null);

  // v1.0.0 — 删除「关联物业」字段(后端自动挑 first active 合作物业)
  // 服务商成员实际跨多物业工作,user-facing 不暴露 tenant_id

  const { mutate: create, mutation } = useCreate();

  function submit() {
    setError(null);
    if (!name.trim()) {
      setError("姓名不能为空");
      return;
    }
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      setError("手机号格式不正确(11 位 1 开头)");
      return;
    }
    create(
      {
        resource: "provider/team",
        values: {
          name: name.trim(),
          phone,
          role,
          // v1.0.0 — 不再传 tenant_id;后端自动挑 first active 合作物业
          // v0.7.0 — 不再传 password,改 OTP 首登
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
    <RightDrawer
      open
      onClose={onClose}
      drawerKey="provider-team-create"
      defaultWidth={520}
      title={
        <span className="flex items-center gap-2">
          <UserPlus className="w-5 h-5 text-[var(--color-primary)]" />
          新建团队成员
        </span>
      }
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={mutation.isPending}
            className="px-4 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            创建成员
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="text-xs text-[var(--color-neutral-600)] bg-[var(--color-neutral-50)] rounded p-2">
          <strong>登录方式</strong>:员工首次登录通过<strong>手机 + 短信验证码</strong>
          (与物业管理员侧一致),无需为员工设置初始密码,登录后可自行管理凭证。
        </div>

        <div className="form-group">
          <label className="form-label">
            姓名 <span className="text-red-500">*</span>
          </label>
          <input
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="请输入员工姓名"
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            手机号 <span className="text-red-500">*</span>
          </label>
          <input
            className="form-control"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="11 位手机号(1 开头)"
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            角色 <span className="text-red-500">*</span>
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

        {/* v1.0.0 — 已删除「关联物业」字段(服务商成员跨物业工作,
            后端自动挑首个有效合作物业作为挂载点) */}

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
    </RightDrawer>
  );
}
