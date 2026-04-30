import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

interface FormData {
  name: string;
  admin_phone: string;
  credit_code: string;
  plan: string;
  monthly_minute_quota: string;
}

export function TenantNewPage() {
  const go = useGo();
  const { mutate: create, mutation: createMutation } = useCreate();
  const isPending = createMutation.isPending;
  const [form, setForm] = useState<FormData>({
    name: "",
    admin_phone: "",
    credit_code: "",
    plan: "trial",
    monthly_minute_quota: "",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleChange =
    (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    create(
      {
        resource: "ops/tenants",
        values: {
          name: form.name,
          admin_phone: form.admin_phone,
          credit_code: form.credit_code || undefined,
          plan: form.plan,
          monthly_minute_quota: form.monthly_minute_quota
            ? Number(form.monthly_minute_quota)
            : undefined,
        },
      },
      {
        onSuccess: () => go({ to: "/ops/tenants" }),
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
          onClick={() => go({ to: "/ops/tenants" })}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新建租户
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        {(
          [
            {
              label: "租户名称 *",
              field: "name" as const,
              type: "text",
              placeholder: "例：XX物业管理有限公司",
              required: true,
            },
            {
              label: "管理员手机 *",
              field: "admin_phone" as const,
              type: "tel",
              placeholder: "138xxxxxxxx",
              required: true,
            },
            {
              label: "统一社会信用代码",
              field: "credit_code" as const,
              type: "text",
              placeholder: "选填",
              required: false,
            },
            {
              label: "月配额（分钟）",
              field: "monthly_minute_quota" as const,
              type: "number",
              placeholder: "留空表示不限",
              required: false,
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
              min={type === "number" ? 0 : undefined}
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        ))}

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            套餐
          </label>
          <select
            value={form.plan}
            onChange={handleChange("plan")}
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="trial">试用</option>
            <option value="standard">标准版</option>
            <option value="premium">高级版</option>
          </select>
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
            {isPending ? "提交中…" : "创建租户"}
          </button>
          <button
            type="button"
            onClick={() => go({ to: "/ops/tenants" })}
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
