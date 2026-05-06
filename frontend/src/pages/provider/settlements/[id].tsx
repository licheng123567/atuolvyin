// frontend/src/pages/provider/settlements/[id].tsx
//
// PA.3.4 — Provider settlement detail (read-only).
import { useGo, useOne } from "@refinedev/core";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";
import { formatRevenue } from "../helpers";
import {
  formatPeriod,
  getStatusColor,
  STATUS_LABELS,
  type SettlementStatus,
} from "../../admin/settlements/helpers";

interface DisputeRecord {
  id: number;
  statement_id: number;
  reason: string;
  status: string;
  resolution: string | null;
  submitted_by: number;
  created_at: string | null;
  updated_at: string | null;
}

interface ProviderSettlementDetail {
  id: number;
  contract_id: number;
  tenant_id: number;
  tenant_name: string;
  period_start: string;
  period_end: string;
  total_amount: string;
  status: SettlementStatus;
  payment_proof_url: string | null;
  confirmed_at: string | null;
  paid_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  disputes: DisputeRecord[];
}

export function ProviderSettlementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<ProviderSettlementDetail>({
    resource: "provider/settlements",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>
    );
  }
  if (!detail) {
    return <div className="text-sm text-red-600 p-8">结算单不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => go({ to: "/provider/settlements" })}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
            aria-label="返回"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            结算单详情
          </h1>
          <span
            className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getStatusColor(detail.status)}`}
          >
            {STATUS_LABELS[detail.status] ?? detail.status}
          </span>
        </div>
        <div className="text-xs text-[var(--color-neutral-400)]">
          仅查看 — 状态变更由租户方操作
        </div>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="space-y-4">
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              结算明细
            </h2>
            <dl className="space-y-3 text-sm">
              <Row label="租户" value={detail.tenant_name} />
              <Row
                label="结算期间"
                value={formatPeriod(detail.period_start, detail.period_end)}
              />
              <Row
                label="金额"
                value={
                  <span className="text-2xl font-semibold text-[var(--color-neutral-900)]">
                    {formatRevenue(detail.total_amount)}
                  </span>
                }
              />
              <Row
                label="确认时间"
                value={
                  detail.confirmed_at
                    ? new Date(detail.confirmed_at).toLocaleString("zh-CN")
                    : "—"
                }
              />
              <Row
                label="支付时间"
                value={
                  detail.paid_at
                    ? new Date(detail.paid_at).toLocaleString("zh-CN")
                    : "—"
                }
              />
            </dl>
          </div>

          {detail.payment_proof_url && (
            <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
              <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">
                付款凭证
              </h2>
              <a
                href={detail.payment_proof_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-[var(--color-primary)] hover:underline break-all"
              >
                <ExternalLink className="w-4 h-4" />
                {detail.payment_proof_url}
              </a>
            </div>
          )}
        </div>

        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            争议历史
          </h2>
          {detail.disputes.length === 0 ? (
            <div className="text-sm text-[var(--color-neutral-400)]">
              暂无争议记录
            </div>
          ) : (
            <ul className="space-y-3">
              {detail.disputes.map((d) => (
                <li
                  key={d.id}
                  className="border border-[var(--color-neutral-100)] rounded-md p-3"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-[var(--color-neutral-700)]">
                      {d.status === "open"
                        ? "未解决"
                        : d.status === "resolved"
                          ? "已解决"
                          : "已驳回"}
                    </span>
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {d.created_at
                        ? new Date(d.created_at).toLocaleString("zh-CN")
                        : "—"}
                    </span>
                  </div>
                  <div className="text-sm text-[var(--color-neutral-900)]">
                    {d.reason}
                  </div>
                  {d.resolution && (
                    <div className="text-xs text-[var(--color-neutral-600)] mt-2">
                      处理意见：{d.resolution}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-xs text-[var(--color-neutral-500)] pt-1">{label}</dt>
      <dd className="text-right text-[var(--color-neutral-900)]">{value}</dd>
    </div>
  );
}
