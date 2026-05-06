import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

interface FormData {
  name: string;
  provider_type: "legal" | "collection" | "both";
  admin_phone: string;
  contact_email: string;
  monthly_minute_quota: string;
  description: string;
}

export function ProviderNewPage() {
  const go = useGo();
  const { mutate: create, mutation: createMutation } = useCreate();
  const isPending = createMutation.isPending;
  const [form, setForm] = useState<FormData>({
    name: "",
    provider_type: "collection",
    admin_phone: "",
    contact_email: "",
    monthly_minute_quota: "",
    description: "",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleChange =
    (field: keyof FormData) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >,
    ) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    create(
      {
        resource: "ops/providers",
        values: {
          name: form.name,
          provider_type: form.provider_type,
          admin_phone: form.admin_phone,
          contact_email: form.contact_email || undefined,
          description: form.description || undefined,
          monthly_minute_quota: form.monthly_minute_quota
            ? Number(form.monthly_minute_quota)
            : undefined,
        },
      },
      {
        onSuccess: () => go({ to: "/ops/providers" }),
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
          onClick={() => go({ to: "/ops/providers" })}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新增服务商
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            服务商名称 *
          </label>
          <input
            type="text"
            value={form.name}
            onChange={handleChange("name")}
            placeholder="例：XX律师事务所"
            required
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            服务类型 *
          </label>
          <select
            value={form.provider_type}
            onChange={handleChange("provider_type")}
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="legal">法务</option>
            <option value="collection">催收</option>
            <option value="both">法务+催收</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            管理员手机 *
          </label>
          <input
            type="tel"
            value={form.admin_phone}
            onChange={handleChange("admin_phone")}
            placeholder="138xxxxxxxx"
            required
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            联系邮箱
          </label>
          <input
            type="email"
            value={form.contact_email}
            onChange={handleChange("contact_email")}
            placeholder="选填"
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            月配额（分钟）
          </label>
          <input
            type="number"
            min={0}
            value={form.monthly_minute_quota}
            onChange={handleChange("monthly_minute_quota")}
            placeholder="留空表示不限"
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            简介
          </label>
          <textarea
            value={form.description}
            onChange={handleChange("description")}
            placeholder="服务范围、资质、联系人等"
            rows={3}
            className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
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
            {isPending ? "提交中…" : "提交审核"}
          </button>
          <button
            type="button"
            onClick={() => go({ to: "/ops/providers" })}
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
