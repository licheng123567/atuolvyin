import { useGo, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

interface TenantDetail {
  id: number;
  name: string;
  credit_code: string | null;
  admin_phone_masked: string;
  plan: string;
  monthly_minute_quota: number | null;
  is_active: boolean;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: "试用",
  standard: "标准版",
  premium: "高级版",
};

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const { query } = useOne<TenantDetail>({
    resource: "ops/tenants",
    id: id ?? "",
  });
  const { mutate: update, mutation: updateMutation } = useUpdate();
  const isPending = updateMutation.isPending;

  const [quota, setQuota] = useState("");
  const [quotaMsg, setQuotaMsg] = useState("");

  const tenant = query.data?.data;
  const isLoading = query.isLoading;

  const handleQuotaSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setQuotaMsg("");
    update(
      {
        resource: `ops/tenants/${id}/quota`,
        id: "",
        values: { monthly_minute_quota: Number(quota) },
      },
      {
        onSuccess: () => {
          setQuotaMsg("配额已更新");
          setQuota("");
        },
        onError: (err) => {
          const e = err as { message?: string };
          setQuotaMsg(e.message ?? "更新失败");
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--color-neutral-400)]">加载中…</div>
    );
  }
  if (!tenant) {
    return (
      <div className="text-sm text-[var(--color-danger)]">租户不存在</div>
    );
  }

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
          {tenant.name}
        </h1>
      </div>

      {/* Info card */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 mb-4">
        <h2 className="text-sm font-semibold text-[var(--color-neutral-700)] mb-4">
          基本信息
        </h2>
        <dl className="space-y-3 text-sm">
          {(
            [
              ["套餐", PLAN_LABELS[tenant.plan] ?? tenant.plan],
              ["管理员手机", tenant.admin_phone_masked],
              ["社会信用代码", tenant.credit_code ?? "—"],
              ["状态", tenant.is_active ? "正常" : "停用"],
              [
                "月配额（分钟）",
                tenant.monthly_minute_quota?.toString() ?? "不限",
              ],
              [
                "创建时间",
                new Date(tenant.created_at).toLocaleDateString("zh-CN"),
              ],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt className="text-[var(--color-neutral-500)]">{k}</dt>
              <dd className="font-medium text-[var(--color-neutral-900)]">
                {v}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Quota update */}
      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6">
        <h2 className="text-sm font-semibold text-[var(--color-neutral-700)] mb-4">
          更新月配额
        </h2>
        <form onSubmit={handleQuotaSubmit} className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
              新配额（分钟）
            </label>
            <input
              type="number"
              min={0}
              max={100000}
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
              placeholder="输入分钟数"
              required
              className="w-full px-3 py-2 border border-[var(--color-neutral-200)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <button
            type="submit"
            disabled={isPending || !quota}
            className="px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "更新中…" : "确认"}
          </button>
        </form>
        {quotaMsg && (
          <p className="text-xs mt-2 text-[var(--color-neutral-600)]">
            {quotaMsg}
          </p>
        )}
      </div>
    </div>
  );
}
