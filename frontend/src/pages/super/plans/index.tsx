// Sprint 15 — Plan Config CRUD page (SA.1.3)
import { useApiUrl, useCustom, useCustomMutation } from "@refinedev/core";
import { Package, Plus, X } from "lucide-react";
import { useState } from "react";
import { formatMinutes, formatPrice } from "../helpers";

interface PlanConfig {
  id: number;
  plan_name: string;
  display_name: string;
  monthly_minutes: number;
  price_monthly: string | number;
  features: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface PlanFormState {
  plan_name: string;
  display_name: string;
  monthly_minutes: string;
  price_monthly: string;
  features_json: string;
}

const DEFAULT_FORM: PlanFormState = {
  plan_name: "",
  display_name: "",
  monthly_minutes: "0",
  price_monthly: "0",
  features_json: "{}",
};

export function SuperPlansPage() {
  const apiUrl = useApiUrl();
  const { query } = useCustom<PlanConfig[]>({
    url: "super/plans",
    method: "get",
  });
  const { mutate: postMutate, mutation: postMutation } = useCustomMutation();
  const { mutate: patchMutate, mutation: patchMutation } = useCustomMutation();
  const isPosting = postMutation.isPending;
  const isPatching = patchMutation.isPending;
  const refetch = query.refetch;

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<PlanConfig | null>(null);
  const [form, setForm] = useState<PlanFormState>(DEFAULT_FORM);
  const [error, setError] = useState<string | null>(null);

  const isLoading = query.isLoading;
  // useList 在 simple-rest+FastAPI 下，data 可能是 array 或 {items,total} wrapper
  const rawData = query.data?.data as unknown;
  const plans: PlanConfig[] = Array.isArray(rawData)
    ? (rawData as PlanConfig[])
    : ((rawData as { items?: PlanConfig[] } | undefined)?.items ?? []);

  const openCreate = () => {
    setEditing(null);
    setForm(DEFAULT_FORM);
    setError(null);
    setShowForm(true);
  };

  const openEdit = (plan: PlanConfig) => {
    setEditing(plan);
    setForm({
      plan_name: plan.plan_name,
      display_name: plan.display_name,
      monthly_minutes: String(plan.monthly_minutes),
      price_monthly: String(plan.price_monthly),
      features_json: JSON.stringify(plan.features ?? {}, null, 2),
    });
    setError(null);
    setShowForm(true);
  };

  const submit = () => {
    setError(null);
    let features: Record<string, unknown>;
    try {
      features = JSON.parse(form.features_json || "{}");
    } catch {
      setError("Features 不是有效的 JSON");
      return;
    }
    const monthly_minutes = Number.parseInt(form.monthly_minutes, 10);
    const price_monthly = Number.parseFloat(form.price_monthly);
    if (Number.isNaN(monthly_minutes) || Number.isNaN(price_monthly)) {
      setError("月分钟数和价格必须是数字");
      return;
    }

    if (editing) {
      patchMutate(
        {
          url: `${apiUrl}/super/plans/${editing.id}`,
          method: "patch",
          values: {
            display_name: form.display_name,
            monthly_minutes,
            price_monthly,
            features,
          },
        },
        {
          onSuccess: () => {
            setShowForm(false);
            refetch();
          },
          onError: (err) => {
            setError((err as { message?: string })?.message ?? "保存失败");
          },
        },
      );
    } else {
      postMutate(
        {
          url: `${apiUrl}/super/plans`,
          method: "post",
          values: {
            plan_name: form.plan_name,
            display_name: form.display_name,
            monthly_minutes,
            price_monthly,
            features,
            is_active: true,
          },
        },
        {
          onSuccess: () => {
            setShowForm(false);
            refetch();
          },
          onError: (err) => {
            setError((err as { message?: string })?.message ?? "创建失败");
          },
        },
      );
    }
  };

  const toggleActive = (plan: PlanConfig) => {
    patchMutate(
      {
        url: `${apiUrl}/super/plans/${plan.id}/active`,
        method: "patch",
        values: { is_active: !plan.is_active },
      },
      { onSuccess: () => refetch() },
    );
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Package className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            套餐配置
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {plans.length} 个套餐
          </span>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white"
          style={{
            background: "var(--color-primary)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <Plus className="w-4 h-4" />
          新增套餐
        </button>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                套餐编码
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                显示名
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                月分钟
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--color-neutral-600)]">
                月价
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                功能
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                状态
              </th>
              <th className="px-4 py-2 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--color-neutral-500)]">
                  加载中…
                </td>
              </tr>
            ) : plans.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--color-neutral-500)]">
                  暂无套餐
                </td>
              </tr>
            ) : (
              plans.map((p: PlanConfig) => (
                <tr key={p.id} className="border-b border-[var(--color-neutral-100)]">
                  <td className="px-4 py-2 font-mono text-xs">{p.plan_name}</td>
                  <td className="px-4 py-2 font-medium">{p.display_name}</td>
                  <td className="px-4 py-2 text-right">{formatMinutes(p.monthly_minutes)}</td>
                  <td className="px-4 py-2 text-right">{formatPrice(p.price_monthly)}</td>
                  <td className="px-4 py-2 text-xs text-[var(--color-neutral-500)] truncate max-w-xs">
                    {Object.keys(p.features ?? {})
                      .filter((k) => Boolean((p.features as Record<string, unknown>)[k]))
                      .join(", ") || "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        p.is_active
                          ? "inline-block px-2 py-0.5 text-xs rounded bg-green-50 text-green-700"
                          : "inline-block px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600"
                      }
                    >
                      {p.is_active ? "已启用" : "已停用"}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => openEdit(p)}
                        className="text-[var(--color-primary)] hover:underline text-xs"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActive(p)}
                        disabled={isPatching}
                        className="text-[var(--color-neutral-600)] hover:underline text-xs"
                      >
                        {p.is_active ? "停用" : "启用"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Form modal */}
      {showForm && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setShowForm(false)}
        >
          <div
            className="bg-white p-5 rounded-lg w-[520px]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold">
                {editing ? `编辑套餐 #${editing.id}` : "新增套餐"}
              </h2>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="p-1 hover:bg-[var(--color-neutral-100)] rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
                  套餐编码 (plan_name)
                </span>
                <input
                  type="text"
                  value={form.plan_name}
                  disabled={Boolean(editing)}
                  onChange={(e) => setForm({ ...form, plan_name: e.target.value })}
                  className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:bg-[var(--color-neutral-50)]"
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
                  显示名
                </span>
                <input
                  type="text"
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
                    月分钟数
                  </span>
                  <input
                    type="number"
                    value={form.monthly_minutes}
                    onChange={(e) =>
                      setForm({ ...form, monthly_minutes: e.target.value })
                    }
                    className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
                    月价 (元)
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    value={form.price_monthly}
                    onChange={(e) =>
                      setForm({ ...form, price_monthly: e.target.value })
                    }
                    className="w-full px-2 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
                  />
                </label>
              </div>
              <label className="block text-sm">
                <span className="text-xs text-[var(--color-neutral-500)] block mb-1">
                  功能 JSON
                </span>
                <textarea
                  rows={4}
                  value={form.features_json}
                  onChange={(e) =>
                    setForm({ ...form, features_json: e.target.value })
                  }
                  className="w-full px-2 py-1.5 text-xs font-mono border border-[var(--color-neutral-200)] rounded"
                />
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={isPosting || isPatching}
                  className="px-3 py-1.5 text-sm text-white rounded disabled:opacity-50"
                  style={{ background: "var(--color-primary)" }}
                >
                  {editing ? "保存" : "创建"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
