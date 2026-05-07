import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft, Info } from "lucide-react";
import { useState } from "react";

interface FormData {
  name: string;
  phone: string;
  role: string;
}

const ALLOWED_ROLES = [
  { value: "supervisor", label: "主管/督导" },
  { value: "agent_internal", label: "催收员（内部）" },
  { value: "legal", label: "法务专员" },
  { value: "workorder", label: "工单处理员" },
  { value: "project_manager_property", label: "项目负责人（物业）" },
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

  const handleChange =
    (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

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
        },
      },
      {
        onSuccess: () => go({ to: "/admin/users" }),
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "创建失败，请重试");
        },
      },
    );
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
    </div>
  );
}
