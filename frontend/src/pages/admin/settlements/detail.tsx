// frontend/src/pages/admin/settlements/detail.tsx
import { useCustomMutation, useGo, useInvalidate, useOne } from "@refinedev/core";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  formatAmount,
  formatPeriod,
  getActionButtons,
  getStatusColor,
  STATUS_LABELS,
  type SettlementStatus,
} from "./helpers";

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

interface SettlementDetail {
  id: number;
  contract_id: number;
  provider_id: number | null;
  provider_name: string | null;
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

type ModalType = null | "pay" | "dispute";

export function AdminSettlementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();

  const [modal, setModal] = useState<ModalType>(null);
  const [payProofUrl, setPayProofUrl] = useState("");
  const [disputeReason, setDisputeReason] = useState("");

  const { query } = useOne<SettlementDetail>({
    resource: "admin/settlements",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const { mutate: runAction, isLoading: actionLoading } = useCustomMutation();

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  function refresh() {
    if (!detail) return;
    void invalidate({
      resource: "admin/settlements",
      invalidates: ["detail", "list"],
      id: detail.id,
    });
  }

  function handleConfirm() {
    if (!detail) return;
    runAction(
      {
        url: `admin/settlements/${detail.id}/confirm`,
        method: "patch",
        values: {},
      },
      {
        onSuccess: refresh,
        onError: () => alert("确认失败，请重试"),
      },
    );
  }

  function handlePay() {
    if (!detail) return;
    runAction(
      {
        url: `admin/settlements/${detail.id}/pay`,
        method: "patch",
        values: { payment_proof_url: payProofUrl || undefined },
      },
      {
        onSuccess: () => {
          setModal(null);
          setPayProofUrl("");
          refresh();
        },
        onError: () => alert("标记已支付失败，请重试"),
      },
    );
  }

  function handleDispute() {
    if (!detail || !disputeReason.trim()) return;
    runAction(
      {
        url: `admin/settlements/${detail.id}/dispute`,
        method: "post",
        values: { reason: disputeReason.trim() },
      },
      {
        onSuccess: () => {
          setModal(null);
          setDisputeReason("");
          refresh();
        },
        onError: () => alert("发起争议失败，请重试"),
      },
    );
  }

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-red-600 p-8">结算单不存在</div>;
  }

  const buttons = getActionButtons(detail.status);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => go({ to: "/admin/settlements" })}
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

        <div className="flex gap-2">
          {buttons.map((b) => {
            const onClick =
              b.action === "confirm"
                ? handleConfirm
                : b.action === "pay"
                  ? () => setModal("pay")
                  : () => setModal("dispute");
            const variantClass =
              b.variant === "primary"
                ? "bg-[var(--color-primary)] text-white hover:opacity-90"
                : b.variant === "danger"
                  ? "border border-red-300 text-red-600 hover:bg-red-50"
                  : "border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]";
            return (
              <button
                key={b.action}
                type="button"
                onClick={onClick}
                disabled={actionLoading}
                className={`px-3 py-1.5 text-sm rounded-md ${variantClass} disabled:opacity-40`}
              >
                {b.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 1fr" }}>
        {/* Left — main detail */}
        <div className="space-y-4">
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              结算明细
            </h2>
            <dl className="space-y-3 text-sm">
              <Row label="服务商" value={detail.provider_name ?? "—"} />
              <Row
                label="结算期间"
                value={formatPeriod(detail.period_start, detail.period_end)}
              />
              <Row
                label="金额"
                value={
                  <span className="text-2xl font-semibold text-[var(--color-neutral-900)]">
                    {formatAmount(detail.total_amount)}
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

          {/* Payment proof */}
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

        {/* Right — disputes */}
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

      {/* Pay modal */}
      {modal === "pay" && (
        <Modal title="标记已支付" onClose={() => setModal(null)}>
          <p className="text-sm text-[var(--color-neutral-600)] mb-3">
            可填写付款凭证 URL（图片链接，支持留空）。
          </p>
          <input
            type="text"
            value={payProofUrl}
            onChange={(e) => setPayProofUrl(e.target.value)}
            placeholder="https://example.com/proof.jpg"
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
              onClick={handlePay}
              disabled={actionLoading}
              className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "提交中…" : "确认"}
            </button>
          </div>
        </Modal>
      )}

      {/* Dispute modal */}
      {modal === "dispute" && (
        <Modal title="发起争议" onClose={() => setModal(null)}>
          <p className="text-sm text-[var(--color-neutral-600)] mb-3">
            请填写争议原因。提交后，结算单状态将变更为「争议中」。
          </p>
          <textarea
            value={disputeReason}
            onChange={(e) => setDisputeReason(e.target.value)}
            rows={4}
            placeholder="例如：本期结算金额与对账单不符…"
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
              onClick={handleDispute}
              disabled={actionLoading || !disputeReason.trim()}
              className="px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "提交中…" : "提交争议"}
            </button>
          </div>
        </Modal>
      )}
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
