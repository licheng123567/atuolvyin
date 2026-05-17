// v1.5.5 — admin 编辑员工：姓名 / 角色 / 邮箱 / 启用状态 + 重发首登码
import {
  useCustomMutation,
  useGetIdentity,
  useGo,
  useOne,
  useUpdate,
} from "@refinedev/core";
import { ArrowLeft, KeyRound, Mail, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { InviteQrModal } from "../../../components/admin/InviteQrModal";
import type { AuthUser } from "../../../providers/auth-provider";

interface UserDetail {
  id: number;
  name: string;
  phone_masked: string;
  role: string;
  is_active: boolean;
  email?: string | null;
  login_method?: string | null;
  last_login_at?: string | null;
  // v1.5.6 — 多角色
  all_roles?: string[];
}

interface IssueOtpResponse {
  phone_masked: string;
  phone_full: string | null;
  otp: string | null;
}

// v1.5.6 — 物业内部角色（与 new.tsx 同步，scope=tenant:{id}）
const ALLOWED_ROLES = [
  { value: "supervisor", label: "督导" },
  { value: "agent", label: "催收员" },
  { value: "coordinator", label: "协调员" },
  { value: "legal", label: "法务对接人" },
  { value: "project_manager", label: "项目负责人" },
];

export function UserEditPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const { data: identity } = useGetIdentity<AuthUser>();
  const isSelf = identity?.id != null && Number(id) === identity.id;

  const { query } = useOne<UserDetail>({
    resource: "admin/users",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });
  const detail = query.data?.data;

  const [name, setName] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [email, setEmail] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [errMsg, setErrMsg] = useState("");
  const [savedHint, setSavedHint] = useState(false);
  const [invite, setInvite] = useState<IssueOtpResponse | null>(null);

  const { mutate: update, mutation: updateMutation } = useUpdate();
  const { mutate: issueOtp, mutation: otpMutation } = useCustomMutation();

  useEffect(() => {
    if (detail) {
      setName(detail.name);
      setRoles(detail.all_roles && detail.all_roles.length > 0 ? detail.all_roles : [detail.role]);
      setEmail(detail.email ?? "");
      setIsActive(detail.is_active);
    }
  }, [detail]);

  const toggleRole = (r: string) => {
    setRoles((prev) =>
      prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
    );
  };

  const handleSave = () => {
    if (!detail) return;
    setErrMsg("");
    setSavedHint(false);
    const detailRoles = (detail.all_roles && detail.all_roles.length > 0
      ? detail.all_roles
      : [detail.role]
    ).slice().sort();
    const sortedRoles = roles.slice().sort();
    const rolesChanged = JSON.stringify(detailRoles) !== JSON.stringify(sortedRoles);

    const values: Record<string, unknown> = {};
    if (name !== detail.name) values.name = name;
    if (!isSelf && rolesChanged) {
      if (roles.length === 0) {
        setErrMsg("至少选择 1 个角色");
        return;
      }
      values.roles = roles;
    }
    if ((email || null) !== (detail.email ?? null)) values.email = email || null;
    if (!isSelf && isActive !== detail.is_active) values.is_active = isActive;
    if (Object.keys(values).length === 0) {
      setErrMsg("没有需要保存的改动");
      return;
    }
    update(
      { resource: "admin/users", id: detail.id, values },
      {
        onSuccess: () => {
          setSavedHint(true);
          query.refetch();
        },
        onError: (err) => {
          const msg = (err as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message;
          setErrMsg(msg ?? "保存失败");
        },
      },
    );
  };

  const handleIssueOtp = () => {
    if (!detail) return;
    issueOtp(
      { url: `admin/users/${detail.id}/issue-otp`, method: "post", values: {} },
      {
        onSuccess: (resp) => setInvite(resp.data as unknown as IssueOtpResponse),
        onError: () => alert("生成首登码失败"),
      },
    );
  };

  if (query.isLoading) {
    return <div style={{ padding: 24, color: "#9ca3af" }}>加载中…</div>;
  }
  if (!detail) {
    return <div style={{ padding: 24, color: "#e02424" }}>用户不存在</div>;
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <button
          type="button"
          onClick={() => go({ to: "/admin/users" })}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>
        <h1 className="page-title" style={{ margin: 0 }}>编辑员工</h1>
      </div>

      {isSelf && (
        <div style={{
          background: "#fffbeb",
          color: "#92400e",
          padding: "10px 12px",
          borderRadius: 6,
          fontSize: 12,
          marginBottom: 16,
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}>
          <ShieldAlert className="w-4 h-4" />
          这是你自己的账号 — 不能修改自己的角色和启用状态，避免锁死系统。
        </div>
      )}

      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <span className="card-title">基本信息</span>
        </div>
        <div className="card-body" style={{ display: "grid", gridTemplateColumns: "120px 1fr", rowGap: 14, columnGap: 16, alignItems: "center" }}>
          <span className="text-muted" style={{ fontSize: 13 }}>姓名 *</span>
          <input
            className="form-control"
            value={name}
            maxLength={50}
            onChange={(e) => setName(e.target.value)}
            style={{ maxWidth: 320 }}
          />

          <span className="text-muted" style={{ fontSize: 13 }}>角色 *</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {ALLOWED_ROLES.map((r) => {
                const checked = roles.includes(r.value);
                return (
                  <label
                    key={r.value}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 10px",
                      borderRadius: 999,
                      border: checked
                        ? "1px solid var(--color-primary)"
                        : "1px solid var(--color-neutral-200, #e5e7eb)",
                      background: checked ? "var(--color-primary-light, #eff6ff)" : "white",
                      color: checked ? "var(--color-primary)" : "var(--color-neutral-700)",
                      cursor: isSelf ? "not-allowed" : "pointer",
                      fontSize: 13,
                      opacity: isSelf ? 0.6 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={isSelf}
                      onChange={() => toggleRole(r.value)}
                      style={{ width: 12, height: 12 }}
                    />
                    {r.label}
                  </label>
                );
              })}
              {/* admin 等当前用户的角色可能不在 ALLOWED_ROLES 列表中（例如自己是 admin），保底显示 */}
              {roles.filter((r) => !ALLOWED_ROLES.find((ar) => ar.value === r)).map((r) => (
                <span
                  key={r}
                  className="ds-badge ds-badge-purple"
                  style={{ fontSize: 11 }}
                  title="特殊角色（admin 等）由系统管理"
                >
                  {r}（不可改）
                </span>
              ))}
            </div>
            <div style={{ fontSize: 11, color: "#9ca3af" }}>
              {roles.length > 1 && `兼任 ${roles.length} 职 — 登录后可在右上角切换工作角色`}
              {roles.length === 1 && "如需兼任其他岗位，勾选多个角色"}
              {roles.length === 0 && <span style={{ color: "#e02424" }}>至少选择 1 个角色</span>}
            </div>
          </div>

          <span className="text-muted" style={{ fontSize: 13 }}>
            <Mail className="w-3.5 h-3.5" style={{ display: "inline", marginRight: 4, verticalAlign: "-2px" }} />
            邮箱
          </span>
          <input
            className="form-control"
            type="email"
            value={email}
            placeholder="可选"
            maxLength={120}
            onChange={(e) => setEmail(e.target.value.toLowerCase())}
            style={{ maxWidth: 320 }}
          />

          <span className="text-muted" style={{ fontSize: 13 }}>手机号</span>
          <span style={{ fontFamily: "monospace", color: "#6b7280", fontSize: 13 }}>
            {detail.phone_masked}
            <span style={{ marginLeft: 12, fontSize: 12 }}>
              （手机号请由员工本人在「我的账号」修改，或使用下方「重发首登码」让员工重新登录）
            </span>
          </span>

          <span className="text-muted" style={{ fontSize: 13 }}>启用状态</span>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: isSelf ? "not-allowed" : "pointer" }}>
            <input
              type="checkbox"
              checked={isActive}
              disabled={isSelf}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            <span style={{ fontSize: 13 }}>{isActive ? "正常" : "停用（员工无法登录）"}</span>
          </label>
        </div>
      </div>

      <div className="ds-card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <span className="card-title">
            <KeyRound className="inline w-4 h-4 mr-1" style={{ verticalAlign: "-3px" }} />
            首登 OTP
          </span>
        </div>
        <div className="card-body" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "#374151" }}>
            {detail.last_login_at
              ? `员工已登录过（最近 ${new Date(detail.last_login_at).toLocaleDateString("zh-CN")}）`
              : "员工尚未登录"}
          </span>
          <button
            type="button"
            className="ds-btn ds-btn-secondary ds-btn-sm"
            disabled={otpMutation.isPending}
            onClick={handleIssueOtp}
          >
            {otpMutation.isPending ? "生成中…" : "重发首登码"}
          </button>
        </div>
      </div>

      {errMsg && <div style={{ color: "#e02424", fontSize: 13, marginBottom: 12 }}>{errMsg}</div>}
      {savedHint && <div style={{ color: "#057a55", fontSize: 13, marginBottom: 12 }}>✅ 已保存</div>}

      <div style={{ display: "flex", gap: 12 }}>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          disabled={updateMutation.isPending}
          onClick={handleSave}
        >
          {updateMutation.isPending ? "保存中…" : "保存修改"}
        </button>
        <button
          type="button"
          className="ds-btn ds-btn-secondary"
          onClick={() => go({ to: "/admin/users" })}
        >
          取消
        </button>
      </div>

      <InviteQrModal
        open={!!invite}
        onClose={() => setInvite(null)}
        userName={detail.name}
        phoneFull={invite?.phone_full ?? null}
        phoneMasked={invite?.phone_masked ?? detail.phone_masked}
        otp={invite?.otp ?? null}
        devMode={!!invite?.otp}
      />
    </div>
  );
}
