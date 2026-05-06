import {
  useCustomMutation,
  useGo,
  useInvalidate,
  useList,
} from "@refinedev/core";
import { Clock } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import { getTrialUrgencyColor } from "../providers/helpers";

interface TrialItem {
  id: number;
  name: string;
  plan: string;
  admin_phone_masked: string;
  expires_at: string | null;
  days_remaining: number | null;
  is_active: boolean;
  created_at: string;
}

export function TenantTrialPage() {
  const go = useGo();
  const invalidate = useInvalidate();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const [renewModal, setRenewModal] = useState<TrialItem | null>(null);
  const [renewForm, setRenewForm] = useState({
    expires_at: "",
    plan: "standard",
    monthly_minute_quota: "",
  });

  const { query } = useList<TrialItem>({
    resource: "ops/tenants/trial",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
  });

  const rawData = query.data?.data;
  const items: TrialItem[] =
    (rawData as unknown as PaginatedResponse<TrialItem>)?.items ??
    (rawData as TrialItem[] | undefined) ??
    [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isLoading = query.isLoading;

  const { mutate: runAction, isLoading: actionLoading } = useCustomMutation();

  function openRenewModal(t: TrialItem) {
    setRenewForm({
      expires_at: t.expires_at ? t.expires_at.slice(0, 10) : "",
      plan: "standard",
      monthly_minute_quota: "",
    });
    setRenewModal(t);
  }

  function handleRenewSubmit() {
    if (!renewModal || !renewForm.expires_at) return;
    runAction(
      {
        url: `ops/tenants/${renewModal.id}/renew`,
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
          setRenewModal(null);
          void invalidate({
            resource: "ops/tenants/trial",
            invalidates: ["list"],
          });
        },
        onError: () => alert("续费失败，请重试"),
      },
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-[var(--color-primary)]" />
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            试用账号跟进
          </h1>
          <span className="text-sm text-[var(--color-neutral-400)] ml-1">
            共 {total} 家
          </span>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-neutral-50)] border-b border-[var(--color-neutral-200)]">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                租户名称
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                管理员手机
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                到期日
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                剩余天数
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--color-neutral-600)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-neutral-100)]">
            {isLoading && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  加载中…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-[var(--color-neutral-400)]"
                >
                  暂无试用租户
                </td>
              </tr>
            )}
            {items.map((t) => {
              const urgent = t.days_remaining !== null && t.days_remaining <= 3;
              return (
                <tr
                  key={t.id}
                  className={`hover:bg-[var(--color-neutral-50)] ${urgent ? "bg-red-50/40" : ""}`}
                >
                  <td className="px-4 py-3 font-medium text-[var(--color-neutral-900)]">
                    <button
                      type="button"
                      onClick={() => go({ to: `/ops/tenants/${t.id}` })}
                      className="hover:underline"
                    >
                      {t.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {t.admin_phone_masked}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-neutral-600)]">
                    {t.expires_at
                      ? new Date(t.expires_at).toLocaleDateString("zh-CN")
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getTrialUrgencyColor(t.days_remaining)}`}
                    >
                      {t.days_remaining === null
                        ? "未设置"
                        : `${t.days_remaining} 天`}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => openRenewModal(t)}
                      className="text-[var(--color-primary)] hover:underline text-xs"
                    >
                      续费
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            上一页
          </button>
          <span className="text-sm text-[var(--color-neutral-600)]">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-[var(--color-neutral-200)] rounded disabled:opacity-40"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            下一页
          </button>
        </div>
      )}

      {renewModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-label="续费"
        >
          <div className="bg-white rounded-lg shadow-lg w-96 p-5">
            <h3 className="text-base font-semibold mb-3">
              续费 — {renewModal.name}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
                  到期日 *
                </label>
                <input
                  type="date"
                  value={renewForm.expires_at}
                  onChange={(e) =>
                    setRenewForm((f) => ({ ...f, expires_at: e.target.value }))
                  }
                  className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
                  套餐
                </label>
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
              </div>
              <div>
                <label className="block text-xs text-[var(--color-neutral-500)] mb-1">
                  月配额（分钟）
                </label>
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
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => setRenewModal(null)}
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
                {actionLoading ? "提交中…" : "确认续费"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
