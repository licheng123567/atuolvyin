import { useCreate, useGo } from "@refinedev/core";
import { ArrowLeft, ClipboardList } from "lucide-react";
import { useState } from "react";
import {
  WORK_ORDER_PRIORITIES,
  WORK_ORDER_TYPES,
  formatPriority,
  formatType,
  type WorkOrderPriority,
  type WorkOrderType,
} from "./helpers";

interface FormData {
  order_type: WorkOrderType;
  description: string;
  case_id: string;
  call_id: string;
  assigned_to: string;
  priority: WorkOrderPriority;
}

export function WorkOrderNewPage() {
  const go = useGo();
  const { mutate: create, mutation: createMutation } = useCreate();
  const isPending = createMutation.isPending;
  const [form, setForm] = useState<FormData>({
    order_type: "quality",
    description: "",
    case_id: "",
    call_id: "",
    assigned_to: "",
    priority: "normal",
  });
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    create(
      {
        resource: "workorders",
        values: {
          order_type: form.order_type,
          description: form.description,
          case_id: form.case_id ? Number(form.case_id) : undefined,
          call_id: form.call_id ? Number(form.call_id) : undefined,
          assigned_to: form.assigned_to
            ? Number(form.assigned_to)
            : undefined,
          priority: form.priority,
        },
      },
      {
        onSuccess: () => go({ to: "/workorder/orders" }),
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
          onClick={() => go({ to: "/workorder/orders" })}
          className="text-[var(--color-neutral-500)] hover:text-[var(--color-neutral-900)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <ClipboardList className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          新建工单
        </h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg border border-[var(--color-neutral-200)] p-6 space-y-4"
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              工单类型 *
            </label>
            <select
              value={form.order_type}
              onChange={(e) =>
                setForm({
                  ...form,
                  order_type: e.target.value as WorkOrderType,
                })
              }
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              {WORK_ORDER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {formatType(t)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              优先级 *
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
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            描述 *
          </label>
          <textarea
            value={form.description}
            onChange={(e) =>
              setForm({ ...form, description: e.target.value })
            }
            rows={4}
            placeholder="详细描述问题"
            required
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              关联案件 ID（选填）
            </label>
            <input
              type="number"
              min={1}
              value={form.case_id}
              onChange={(e) => setForm({ ...form, case_id: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
              关联通话 ID（选填）
            </label>
            <input
              type="number"
              min={1}
              value={form.call_id}
              onChange={(e) => setForm({ ...form, call_id: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            指派给（用户 ID，选填）
          </label>
          <input
            type="number"
            min={1}
            value={form.assigned_to}
            onChange={(e) =>
              setForm({ ...form, assigned_to: e.target.value })
            }
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        {errorMsg && (
          <p className="text-sm text-[var(--color-danger)]">{errorMsg}</p>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending || !form.description}
            className="flex-1 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            {isPending ? "创建中…" : "创建工单"}
          </button>
          <button
            type="button"
            onClick={() => go({ to: "/workorder/orders" })}
            className="px-4 py-2 text-sm border border-[var(--color-neutral-200)] text-[var(--color-neutral-600)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}
