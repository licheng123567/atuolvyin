import {
  useCustomMutation,
  useGo,
  useInvalidate,
  useOne,
} from "@refinedev/core";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  formatAuditStatus,
  formatProviderType,
  getAuditStatusColor,
} from "./helpers";

interface ContractItem {
  id: number;
  tenant_id: number;
  tenant_name: string;
  signed_at: string;
  expires_at: string | null;
  service_types: string[];
  status: string;
}

interface ProviderDetail {
  id: number;
  name: string;
  provider_type: string;
  admin_phone_masked: string;
  contact_email: string | null;
  description: string | null;
  monthly_minute_quota: number | null;
  is_active: boolean;
  audit_status: string;
  audit_reason: string | null;
  audit_at: string | null;
  created_at: string;
  contracts: ContractItem[];
}

type ModalType = null | "reject" | "edit";

export function ProviderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();

  const [modal, setModal] = useState<ModalType>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    contact_email: "",
    monthly_minute_quota: "",
  });

  const { query } = useOne<ProviderDetail>({
    resource: "ops/providers",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const { mutate: runAction, mutation: actionMutation } = useCustomMutation();
  const actionLoading = actionMutation.isPending;

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  function refresh() {
    if (!detail) return;
    void invalidate({
      resource: "ops/providers",
      invalidates: ["detail", "list"],
      id: detail.id,
    });
  }

  function handleApprove() {
    if (!detail) return;
    runAction(
      {
        url: `ops/providers/${detail.id}/audit`,
        method: "patch",
        values: { decision: "approved" },
      },
      {
        onSuccess: refresh,
        onError: () => alert("审核通过失败，请重试"),
      },
    );
  }

  function handleReject() {
    if (!detail || !rejectReason.trim()) return;
    runAction(
      {
        url: `ops/providers/${detail.id}/audit`,
        method: "patch",
        values: { decision: "rejected", reason: rejectReason.trim() },
      },
      {
        onSuccess: () => {
          setModal(null);
          setRejectReason("");
          refresh();
        },
        onError: () => alert("驳回失败，请重试"),
      },
    );
  }

  function handleToggleActive() {
    if (!detail) return;
    runAction(
      {
        url: `ops/providers/${detail.id}/active`,
        method: "patch",
        values: { is_active: !detail.is_active },
      },
      {
        onSuccess: refresh,
        onError: () => alert("操作失败，请重试"),
      },
    );
  }

  function openEditModal() {
    if (!detail) return;
    setEditForm({
      name: detail.name,
      description: detail.description ?? "",
      contact_email: detail.contact_email ?? "",
      monthly_minute_quota: detail.monthly_minute_quota?.toString() ?? "",
    });
    setModal("edit");
  }

  function handleEditSubmit() {
    if (!detail) return;
    runAction(
      {
        url: `ops/providers/${detail.id}`,
        method: "patch",
        values: {
          name: editForm.name,
          description: editForm.description || undefined,
          contact_email: editForm.contact_email || undefined,
          monthly_minute_quota: editForm.monthly_minute_quota
            ? Number(editForm.monthly_minute_quota)
            : undefined,
        },
      },
      {
        onSuccess: () => {
          setModal(null);
          refresh();
        },
        onError: () => alert("保存失败，请重试"),
      },
    );
  }

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>
    );
  }
  if (!detail) {
    return <div className="text-sm text-red-600 p-8">服务商不存在</div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => go({ to: "/ops/providers" })}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
            aria-label="返回"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
            {detail.name}
          </h1>
          <span
            className={`inline-flex px-2 py-0.5 text-xs rounded-full font-medium ${getAuditStatusColor(detail.audit_status)}`}
          >
            {formatAuditStatus(detail.audit_status)}
          </span>
        </div>

        <div className="flex gap-2">
          {detail.audit_status === "pending" && (
            <>
              <button
                type="button"
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
              >
                审核通过
              </button>
              <button
                type="button"
                onClick={() => setModal("reject")}
                disabled={actionLoading}
                className="px-3 py-1.5 text-sm rounded-md border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40"
              >
                驳回
              </button>
            </>
          )}
          <button
            type="button"
            onClick={handleToggleActive}
            disabled={actionLoading}
            className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)] disabled:opacity-40"
          >
            {detail.is_active ? "停用" : "启用"}
          </button>
          <button
            type="button"
            onClick={openEditModal}
            className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-50)]"
          >
            编辑信息
          </button>
        </div>
      </div>

      {/* Banner — rejected reason */}
      {detail.audit_status === "rejected" && detail.audit_reason && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-md px-4 py-3 mb-4 text-sm">
          已驳回：{detail.audit_reason}
        </div>
      )}

      <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 1fr" }}>
        {/* Left — info */}
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            基本信息
          </h2>
          <dl className="space-y-3 text-sm">
            <Row
              label="服务类型"
              value={formatProviderType(detail.provider_type)}
            />
            <Row label="管理员手机" value={detail.admin_phone_masked} />
            <Row label="联系邮箱" value={detail.contact_email ?? "—"} />
            <Row
              label="月配额（分钟）"
              value={detail.monthly_minute_quota?.toString() ?? "不限"}
            />
            <Row
              label="运营状态"
              value={detail.is_active ? "正常" : "停用"}
            />
            <Row label="简介" value={detail.description ?? "—"} />
            <Row
              label="创建时间"
              value={new Date(detail.created_at).toLocaleString("zh-CN")}
            />
          </dl>
        </div>

        {/* Right — contracts */}
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            合作物业（{detail.contracts.length}）
          </h2>
          {detail.contracts.length === 0 ? (
            <div className="text-sm text-[var(--color-neutral-400)]">
              暂无合作记录
            </div>
          ) : (
            <ul className="space-y-3">
              {detail.contracts.map((c) => (
                <li
                  key={c.id}
                  className="border border-[var(--color-neutral-100)] rounded-md p-3"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-[var(--color-neutral-900)]">
                      {c.tenant_name}
                    </span>
                    <span className="text-xs text-[var(--color-neutral-500)]">
                      {c.status === "active" ? "执行中" : c.status}
                    </span>
                  </div>
                  <div className="text-xs text-[var(--color-neutral-500)]">
                    服务类型：{c.service_types.join(", ")}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-500)] mt-1">
                    签订：
                    {new Date(c.signed_at).toLocaleDateString("zh-CN")}
                    {c.expires_at &&
                      ` · 到期：${new Date(c.expires_at).toLocaleDateString("zh-CN")}`}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Reject modal */}
      {modal === "reject" && (
        <Modal title="驳回服务商" onClose={() => setModal(null)}>
          <p className="text-sm text-[var(--color-neutral-600)] mb-3">
            请填写驳回原因。提交后服务商将无法上线。
          </p>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={4}
            placeholder="例如：营业执照模糊、资质不全等"
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
              onClick={handleReject}
              disabled={actionLoading || !rejectReason.trim()}
              className="px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "提交中…" : "确认驳回"}
            </button>
          </div>
        </Modal>
      )}

      {/* Edit modal */}
      {modal === "edit" && (
        <Modal title="编辑服务商信息" onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Field label="名称">
              <input
                type="text"
                value={editForm.name}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, name: e.target.value }))
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </Field>
            <Field label="联系邮箱">
              <input
                type="email"
                value={editForm.contact_email}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, contact_email: e.target.value }))
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </Field>
            <Field label="月配额（分钟）">
              <input
                type="number"
                min={0}
                value={editForm.monthly_minute_quota}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    monthly_minute_quota: e.target.value,
                  }))
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </Field>
            <Field label="简介">
              <textarea
                value={editForm.description}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, description: e.target.value }))
                }
                rows={3}
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
              onClick={handleEditSubmit}
              disabled={actionLoading}
              className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
            >
              {actionLoading ? "保存中…" : "保存"}
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
      <dd className="text-right text-[var(--color-neutral-900)] break-all">
        {value}
      </dd>
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
