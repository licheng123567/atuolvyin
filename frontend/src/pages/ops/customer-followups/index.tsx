// Sprint 10.2 — 平台运营员客户跟进记录（PRD §L2000）
import { useCustom, useCustomMutation, useList } from "@refinedev/core";
import { MessageCircle, Plus, X } from "lucide-react";
import { useState } from "react";

interface FollowupItem {
  id: number;
  tenant_id: number;
  tenant_name: string | null;
  note: string;
  follow_up_at: string | null;
  created_by: number;
  created_at: string;
}

interface TenantOption {
  id: number;
  name: string;
}

export function OpsCustomerFollowupsPage() {
  const [tenantFilter, setTenantFilter] = useState<number | null>(null);
  const [showNew, setShowNew] = useState(false);

  const { query } = useCustom<FollowupItem[]>({
    url: "ops/customer-followups",
    method: "get",
    config: {
      query: tenantFilter ? { tenant_id: tenantFilter } : undefined,
    },
  });
  const items = query.data?.data ?? [];

  // For tenant dropdown — leverage existing /ops/tenants list
  const tenantsListing = useList<TenantOption>({
    resource: "ops/tenants",
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const tenants = (tenantsListing.query.data?.data as unknown as { items?: TenantOption[] })?.items
    ?? (tenantsListing.query.data?.data as TenantOption[] | undefined)
    ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <MessageCircle className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">客户跟进记录</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          共 {items.length} 条
        </span>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={tenantFilter ?? ""}
            onChange={(e) =>
              setTenantFilter(e.target.value ? Number(e.target.value) : null)
            }
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            <option value="">全部租户</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Plus className="w-4 h-4" />
            新建跟进
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {items.length === 0 && !query.isLoading && (
          <p className="text-sm text-[var(--color-neutral-400)] py-8 text-center">
            暂无跟进记录
          </p>
        )}
        {items.map((it) => (
          <div
            key={it.id}
            className="bg-white p-4 border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-lg)" }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold">
                {it.tenant_name ?? `租户 #${it.tenant_id}`}
              </span>
              {it.follow_up_at && (
                <span className="text-xs text-[var(--color-warning)]">
                  下次跟进：{it.follow_up_at?.slice(0, 16).replace("T", " ")}
                </span>
              )}
            </div>
            <p className="text-sm text-[var(--color-neutral-700)] whitespace-pre-wrap">
              {it.note}
            </p>
            <p className="text-xs text-[var(--color-neutral-400)] mt-2">
              创建于 {it.created_at?.slice(0, 19).replace("T", " ")}
            </p>
          </div>
        ))}
      </div>

      {showNew && (
        <NewFollowupDialog
          tenants={tenants}
          onClose={() => setShowNew(false)}
          onSaved={() => {
            setShowNew(false);
            query.refetch();
          }}
        />
      )}
    </div>
  );
}

function NewFollowupDialog({
  tenants,
  onClose,
  onSaved,
}: {
  tenants: TenantOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [tenantId, setTenantId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [followUpAt, setFollowUpAt] = useState("");
  const [error, setError] = useState("");
  const { mutate: create, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!tenantId) {
      setError("请选择租户");
      return;
    }
    if (!note.trim()) {
      setError("请填写跟进内容");
      return;
    }
    create(
      {
        url: "ops/customer-followups",
        method: "post",
        values: {
          tenant_id: tenantId,
          note: note.trim(),
          follow_up_at: followUpAt
            ? new Date(followUpAt).toISOString()
            : null,
        },
      },
      {
        onSuccess: onSaved,
        onError: () => setError("保存失败"),
      },
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="bg-white p-6 w-[480px]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">新建跟进记录</h2>
          <button type="button" onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              租户
            </label>
            <select
              value={tenantId ?? ""}
              onChange={(e) =>
                setTenantId(e.target.value ? Number(e.target.value) : null)
              }
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              <option value="">请选择…</option>
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              跟进内容
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={5}
              placeholder="电话沟通要点 / 客户反馈 / 待办事项"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              下次跟进时间（可选）
            </label>
            <input
              type="datetime-local"
              value={followUpAt}
              onChange={(e) => setFollowUpAt(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              取消
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={mutation.isPending}
              className="px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              {mutation.isPending ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
