import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft, Info } from "lucide-react";
import { useState } from "react";
import { InviteQrModal } from "../../../components/admin/InviteQrModal";

interface FormData {
  name: string;
  phone: string;
  role: string;
}

interface CreateUserResponse {
  id: number;
  name: string;
  phone_masked: string;
  initial_otp?: string | null;
  phone_full?: string | null;
}

// v1.5.6 — 物业内部角色（不含 project_manager_provider；那是服务商组织角色）
const ALLOWED_ROLES = [
  { value: "supervisor", label: "督导（实时质检 + 团队组长）" },
  { value: "agent_internal", label: "内部催收员（拨打电话 / 跟进案件）" },
  { value: "coordinator", label: "协调员（接服务商工单 + 调度物业各职能）" },
  { value: "legal", label: "法务对接人（审核转法务 + 跟律所沟通）" },
  { value: "project_manager_property", label: "项目负责人（按项目跟进）" },
];

export function UserNewPage() {
  const go = useGo();
  const { mutate: create, mutation: createMutation } = useCreate();
  const isPending = createMutation.isPending;
  const [form, setForm] = useState<FormData>({
    name: "",
    phone: "",
    role: "supervisor",
  });
  const [errorMsg, setErrorMsg] = useState("");
  const [invite, setInvite] = useState<CreateUserResponse | null>(null);
  // v1.5.6 — 一人多角色：可选追加角色（与主 role 分开记录）
  const [extraRoles, setExtraRoles] = useState<string[]>([]);

  const handleChange =
    (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const toggleExtraRole = (r: string) => {
    if (r === form.role) return;
    setExtraRoles((prev) =>
      prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    // v1.4 方案 A — 创建时不传 password；员工首次登录走「手机+验证码」
    create(
      {
        resource: "admin/users",
        values: {
          name: form.name,
          phone: form.phone,
          role: form.role,
          extra_roles: extraRoles,
        },
      },
      {
        onSuccess: (resp) => {
          const data = resp.data as unknown as CreateUserResponse;
          setInvite(data);
        },
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "创建失败，请重试");
        },
      },
    );
  };

  const closeInvite = () => {
    setInvite(null);
    go({ to: "/admin/users" });
  };

  return (
    <div className="max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/users" })}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新建用户
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        {(
          [
            {
              label: "姓名 *",
              field: "name" as const,
              type: "text",
              placeholder: "例：张三",
              required: true,
            },
            {
              label: "手机 *",
              field: "phone" as const,
              type: "tel",
              placeholder: "138xxxxxxxx",
              required: true,
            },
          ] as const
        ).map(({ label, field, type, placeholder, required }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              {label}
            </label>
            <input
              type={type}
              value={form[field]}
              onChange={handleChange(field)}
              placeholder={placeholder}
              required={required}
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        ))}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            角色 *
          </label>
          <select
            value={form.role}
            onChange={handleChange("role")}
            required
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            {ALLOWED_ROLES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* v1.5.6 — 兼任其他角色（一人多岗）*/}
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            兼任其他岗位（可选，多选）
          </label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {ALLOWED_ROLES.filter((r) => r.value !== form.role).map((r) => {
              const checked = extraRoles.includes(r.value);
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
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleExtraRole(r.value)}
                    style={{ width: 12, height: 12 }}
                  />
                  {r.label.split("（")[0]}
                </label>
              );
            })}
          </div>
          {extraRoles.length > 0 && (
            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
              将创建 {extraRoles.length + 1} 个角色 — 该员工登录后可在右上角切换工作角色
            </div>
          )}
        </div>

        <div
          className="flex items-start gap-2 p-3"
          style={{
            background: "var(--color-primary-light, #eff6ff)",
            border: "1px solid var(--color-primary, #3b82f6)",
            borderRadius: "var(--radius-md)",
            fontSize: 12,
            color: "var(--color-neutral-700, #374151)",
          }}
        >
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-[var(--color-primary)]" />
          <div>
            <strong>无需设置初始密码。</strong>
            员工创建后，首次登录请走「手机验证码」标签 — 输入手机号点「获取验证码」即可登录。登录后可在「我的账号」自愿设置密码。
            <div style={{ marginTop: 6, color: "var(--color-neutral-500, #6b7280)" }}>
              💡 此处只能创建本物业的员工。<strong>外部催收员（外勤）</strong>由对应服务商管理员在自家系统创建；如需邀请新服务商合作，请前往「服务商合作」页推荐入驻。
            </div>
          </div>
        </div>

        {errorMsg && (
          <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending}
            className="flex-1 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "提交中…" : "创建用户"}
          </button>
          <button
            type="button"
            onClick={() => go({ to: "/admin/users" })}
            className="px-4 py-2 text-sm border border-[var(--color-neutral-200)] rounded text-[var(--color-neutral-600)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            取消
          </button>
        </div>
      </form>

      <InviteQrModal
        open={!!invite}
        onClose={closeInvite}
        userName={invite?.name ?? ""}
        phoneFull={invite?.phone_full ?? null}
        phoneMasked={invite?.phone_masked ?? ""}
        otp={invite?.initial_otp ?? null}
        devMode={!!invite?.initial_otp}
      />
    </div>
  );
}
