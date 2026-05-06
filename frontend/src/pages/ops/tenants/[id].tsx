import {
  useCustomMutation,
  useGo,
  useInvalidate,
  useOne,
  useUpdate,
} from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { daysUntil, getTrialUrgencyColor } from "../providers/helpers";

interface TenantDetail {
  id: number;
  name: string;
  credit_code: string | null;
  admin_phone_masked: string;
  plan: string;
  monthly_minute_quota: number | null;
  expires_at: string | null;
  is_active: boolean;
  is_trial: boolean;
  disabled_reason: string | null;
  disabled_at: string | null;
  created_at: string;
}

const PLAN_LABELS: Record<string, string> = {
  trial: "试用",
  standard: "标准版",
  premium: "高级版",
};

type ModalType = null | "renew" | "disable";

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();
  const { query } = useOne<TenantDetail>({
    resource: "ops/tenants",
    id: id ?? "",
  });
  const { mutate: update, mutation: updateMutation } = useUpdate();
  const { mutate: runAction, isLoading: actionLoading } = useCustomMutation();

  const [quota, setQuota] = useState("");
  const [quotaMsg, setQuotaMsg] = useState("");
  const [modal, setModal] = useState<ModalType>(null);
  const [renewForm, setRenewForm] = useState({
    expires_at: "",
    plan: "standard",
    monthly_minute_quota: "",
  });
  const [disableReason, setDisableReason] = useState("");

  const tenant = query.data?.data;
  const isLoading = query.isLoading;
  const isQuotaPending = updateMutation.isPending;

  function refresh() {
    if (!tenant) return;
    void invalidate({
      resource: "ops/tenants",
      invalidates: ["detail", "list"],
      id: tenant.id,
    });
  }

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
          refresh();
        },
        onError: (err) => {
          const e = err as { message?: string };
          setQuotaMsg(e.message ?? "更新失败");
        },
      },
    );
  };

  function openRenewModal() {
    if (!tenant) return;
    setRenewForm({
      expires_at: tenant.expires_at ? tenant.expires_at.slice(0, 10) : "",
      plan: tenant.plan,
      monthly_minute_quota: tenant.monthly_minute_quota?.toString() ?? "",
    });
    setModal("renew");
  }

  function handleRenewSubmit() {
    if (!tenant || !renewForm.expires_at) return;
    runAction(
      {
        url: `ops/tenants/${tenant.id}/renew`,
        method: "patch",
        values: {
          expires_at: new Date(renewForm.expires_at).toISOString(),
          plan: renewForm.plan,
          monthly_minute_quota: renewForm.monthly_minute_quota
            ? Number(renewForm.monthly_minute_quota)
            : undefined,
        },
      },
      {
        onSuccess: () => {
          setModal(null);
          refresh();
        },
        onError: () => alert("续费失败，请重试"),
      },
    );
  }

  function handleDisableSubmit() {
    if (!tenant || !disableReason.trim()) return;
    runAction(
      {
        url: `ops/tenants/${tenant.id}/disable`,
        method: "patch",
        values: { reason: disableReason.trim() },
      },
      {
        onSuccess: () => {
          setModal(null);
          setDisableReason("");
          refresh();
        },
        onError: () => alert("停用失败，请重试"),
      },
    );
  }

  function handleEnable() {
    if (!tenant) return;
    runAction(
      {
        url: `ops/tenants/${tenant.id}/enable`,
        method: "patch",
        values: {},
      },
      {
        onSuccess: refresh,
        onError: () => alert("启用失败，请重试"),
      },
    );
  }

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

  const days = daysUntil(tenant.expires_at);

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
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
          {tenant.is_trial && (
            <span className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium bg-blue-100 text-blue-700">
              试用
            </span>
          )}
          {tenant.expires_at && (
            <span
              className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getTrialUrgencyColor(days)}`}
            >
              {days === null
                ? "—"
                : days === 0
                  ? "已到期"
                  : `${days} 天后到期`}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={openRenewModal}
            disabled={actionLoading}
            className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
          >
            续费 / 变更套餐
          </button>
          {tenant.is_active ? (
            <button
              type="button"
              onClick={() => setModal("disable")}
              disabled={actionLoading}
              className="px-3 py-1.5 text-sm rounded-md border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40"
            >
              停用
            </button>
          ) : (
            <button
              type="button"
              onClick={handleEnable}
              disabled={actionLoading}
              className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)] disabled:opacity-40"
            >
              启用
            </button>
          )}
        </div>
      </div>

      {/* Disabled banner */}
      {!tenant.is_active && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-md px-4 py-3 mb-4 text-sm">
          已停用{tenant.disabled_reason ? `：${tenant.disabled_reason}` : ""}
          {tenant.disabled_at && (
            <span className="ml-2 text-red-500 text-xs">
              （{new Date(tenant.disabled_at).toLocaleString("zh-CN")}）
            </span>
          )}
        </div>
      )}

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
                "到期日",
                tenant.expires_at
                  ? new Date(tenant.expires_at).toLocaleDateString("zh-CN")
                  : "—",
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
            disabled={isQuotaPending || !quota}
            className="px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isQuotaPending ? "更新中…" : "确认"}
          </button>
        </form>
        {quotaMsg && (
          <p className="text-xs mt-2 text-[var(--color-neutral-600)]">
            {quotaMsg}
          </p>
        )}
      </div>

      {/* Renew modal — also used for plan change */}
      {modal === "renew" && (
        <Modal title="续费 / 变更套餐" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Field label="到期日 *">
              <input
                type="date"
                value={renewForm.expires_at}
                onChange={(e) =>
                  setRenewForm((f) => ({ ...f, expires_at: e.target.value }))
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </Field>
            <Field label="套餐">
              <select
                value={renewForm.plan}
                onChange={(e) =>
                  setRenewForm((f) => ({ ...f, plan: e.target.value }))
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
                <option value="trial">试用</option>
                <option value="standard">标准版</option>
                <option value="premium">高级版</option>
              </select>
            </Field>
            <Field label="月配额（分钟）">
              <input
                type="number"
                min={0}
                value={renewForm.monthly_minute_quota}
                onChange={(e) =>
                  setRenewForm((f) => ({
                    ...f,
                    monthly_minute_quota: e.target.value,
                  }))
                }
                placeholder="留空保持现状"
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </Field>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={() => setModal(null)}
              className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleRenewSubmit}
              disabled={actionLoading || !renewForm.expires_at}
              className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "提交中…" : "确认"}
            </button>
          </div>
        </Modal>
      )}

      {/* Disable modal */}
      {modal === "disable" && (
        <Modal title="停用租户" onClose={() => setModal(null)}>
          <p className="text-sm text-[var(--color-neutral-600)] mb-3">
            停用后租户将无法登录，请填写停用原因。
          </p>
          <textarea
            value={disableReason}
            onChange={(e) => setDisableReason(e.target.value)}
            rows={4}
            placeholder="例如：合同到期未续签"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          />
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={() => setModal(null)}
              className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleDisableSubmit}
              disabled={actionLoading || !disableReason.trim()}
              className="px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "提交中…" : "确认停用"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="bg-white rounded-lg shadow-lg w-96 p-5">
        <h3 className="text-base font-semibold mb-3">{title}</h3>
        {children}
        <button
          type="button"
          onClick={onClose}
          className="sr-only"
          aria-label="关闭"
        />
      </div>
    </div>
  );
}
