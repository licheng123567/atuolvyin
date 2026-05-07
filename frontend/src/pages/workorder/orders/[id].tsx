import { useGo, useList, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft, ClipboardList, Save } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { PaginatedResponse, UserRole } from "../../../types";
import {
  WORK_ORDER_PRIORITIES,
  WORK_ORDER_STATUSES,
  formatPriority,
  formatStatus,
  formatType,
  getPriorityColor,
  getStatusColor,
  type WorkOrderPriority,
} from "./helpers";

interface CaseRef {
  id: number;
  stage: string;
  owner_name: string;
  owner_phone_masked: string;
}

interface CallRef {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  result_tag: string | null;
}

interface WorkOrderDetail {
  id: number;
  case_id: number | null;
  call_id: number | null;
  order_type: string;
  description: string;
  assigned_to: number | null;
  status: string;
  priority: string;
  resolution: string | null;
  assignee_name: string | null;
  created_at: string;
  case: CaseRef | null;
  call: CallRef | null;
}

interface AdminUser {
  id: number;
  name: string;
  role: UserRole;
}

interface FormState {
  status: string;
  assigned_to: number | null;
  description: string;
  resolution: string;
  priority: WorkOrderPriority;
}

function detailToForm(detail: WorkOrderDetail): FormState {
  return {
    status: detail.status,
    assigned_to: detail.assigned_to,
    description: detail.description,
    resolution: detail.resolution ?? "",
    priority: (detail.priority as WorkOrderPriority) ?? "normal",
  };
}

export function WorkOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<WorkOrderDetail>({
    resource: "workorders",
    id: id ?? "",
  });
  const detail = query.data?.data;

  // Try to load admin users for assignee picker; if user lacks role, list will be empty.
  const { result: usersResult } = useList<AdminUser>({
    resource: "admin/users",
    pagination: { pageSize: 100 },
    queryOptions: { retry: 0 },
  });
  const rawUsers = usersResult.data;
  const users: AdminUser[] =
    (rawUsers as unknown as PaginatedResponse<AdminUser>)?.items ??
    (rawUsers as AdminUser[] | undefined) ??
    [];

  const [overrideForm, setOverrideForm] = useState<FormState | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const form: FormState = overrideForm ?? (detail
    ? detailToForm(detail)
    : {
        status: "open",
        assigned_to: null,
        description: "",
        resolution: "",
        priority: "normal",
      });

  const setForm = (next: FormState) => setOverrideForm(next);

  const { mutate: update, mutation: updateMutation } = useUpdate();
  const saving = updateMutation.isPending;

  const handleSave = () => {
    if (!detail) return;
    setErrorMsg("");
    update(
      {
        resource: "workorders",
        id: detail.id,
        values: {
          status: form.status,
          assigned_to: form.assigned_to,
          description: form.description,
          resolution: form.resolution || null,
          priority: form.priority,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setOverrideForm(null);
          query.refetch();
        },
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "保存失败");
        },
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-8 text-sm text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!detail) {
    return <div className="p-8 text-sm text-[var(--color-danger)]">工单不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/workorder/orders" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <ClipboardList className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          工单 #{detail.id}
        </h1>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={getStatusColor(detail.status)}
        >
          {formatStatus(detail.status)}
        </span>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={getPriorityColor(detail.priority)}
        >
          {formatPriority(detail.priority)}
        </span>
        <span className="text-xs text-[var(--color-neutral-400)] ml-2">
          类型: {formatType(detail.order_type)}
        </span>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "320px 1fr" }}>
        {/* Left: related case / call */}
        <div className="space-y-4">
          {detail.case && (
            <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5">
              <h3 className="text-sm font-semibold mb-3">关联案件</h3>
              <dl className="text-sm space-y-2">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">业主</dt>
                  <dd className="font-medium">{detail.case.owner_name}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">手机</dt>
                  <dd>{detail.case.owner_phone_masked}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">案件状态</dt>
                  <dd>{detail.case.stage}</dd>
                </div>
              </dl>
              <button
                type="button"
                onClick={() => go({ to: `/admin/cases/${detail.case_id}` })}
                className="mt-3 text-xs text-[var(--color-primary)] hover:underline"
              >
                查看案件 →
              </button>
            </div>
          )}
          {detail.call && (
            <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5">
              <h3 className="text-sm font-semibold mb-3">关联通话</h3>
              <dl className="text-sm space-y-2">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">通话时间</dt>
                  <dd>
                    {detail.call.started_at
                      ? new Date(detail.call.started_at).toLocaleString("zh-CN")
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">时长</dt>
                  <dd>{detail.call.duration_sec ?? "—"}s</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-neutral-500)]">结果</dt>
                  <dd>{detail.call.result_tag ?? "—"}</dd>
                </div>
              </dl>
              <button
                type="button"
                onClick={() => go({ to: `/calls/${detail.call_id}` })}
                className="mt-3 text-xs text-[var(--color-primary)] hover:underline"
              >
                查看通话 →
              </button>
            </div>
          )}
          {!detail.case && !detail.call && (
            <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5">
              <p className="text-sm text-[var(--color-neutral-400)]">
                此工单未关联案件或通话
              </p>
            </div>
          )}
        </div>

        {/* Right: editable form */}
        <div className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              描述
            </label>
            <textarea
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
              rows={3}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              优先级
            </label>
            <select
              value={form.priority}
              onChange={(e) =>
                setForm({
                  ...form,
                  priority: e.target.value as WorkOrderPriority,
                })
              }
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              {WORK_ORDER_PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {formatPriority(p)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                状态
              </label>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                {WORK_ORDER_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {formatStatus(s)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
                负责人
              </label>
              <select
                value={form.assigned_to ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    assigned_to: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
                className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                style={{ borderRadius: "var(--radius-md)" }}
              >
                <option value="">未分配</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}（{u.role}）
                  </option>
                ))}
                {/* If current assigned_to isn't in users list (e.g. user list inaccessible), still show */}
                {form.assigned_to !== null &&
                  !users.some((u) => u.id === form.assigned_to) && (
                    <option value={form.assigned_to}>
                      用户 #{form.assigned_to} (
                      {detail.assignee_name ?? "未知"})
                    </option>
                  )}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              处理结果 / 解决方案
            </label>
            <textarea
              value={form.resolution}
              onChange={(e) =>
                setForm({ ...form, resolution: e.target.value })
              }
              rows={4}
              placeholder="处理过程、解决方案、跟进结果"
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>

          {errorMsg && (
            <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
          )}

          <div className="flex items-center justify-between pt-2">
            {savedAt ? (
              <p className="text-xs text-[var(--color-success)]">
                已保存 ({savedAt})
              </p>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{
                background: "var(--color-primary)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <Save className="w-4 h-4" />
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
