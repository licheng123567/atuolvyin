// Sprint 16.1 — 法务转化订单列表 (PRD §20.4)
import { useCustom, useGo } from "@refinedev/core";
import { Briefcase, FileText, Filter } from "lucide-react";
import { useState } from "react";
import { LegalDocumentModal } from "../../../components/legal-conversion/LegalDocumentModal";

interface OrderItem {
  id: number;
  case_id: number;
  package_id: number;
  package_name: string | null;
  status: "pending" | "dispatched" | "in_service" | "completed" | "cancelled";
  price_quoted: string;
  platform_fee_amount: string;
  assigned_law_firm: string | null;
  assigned_lawyer_name: string | null;
  dispatched_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface ListResp {
  items: OrderItem[];
  total: number;
}

const STATUS_LABEL: Record<OrderItem["status"], string> = {
  pending: "待撮合",
  dispatched: "已派单",
  in_service: "服务中",
  completed: "已完成",
  cancelled: "已取消",
};

const STATUS_COLOR: Record<OrderItem["status"], string> = {
  pending: "bg-gray-100 text-gray-700",
  dispatched: "bg-blue-100 text-blue-700",
  in_service: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-50 text-red-600",
};

export function AdminLegalConversionListPage() {
  const go = useGo();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [docOrderId, setDocOrderId] = useState<number | null>(null);

  const { query } = useCustom<ListResp>({
    url: "admin/legal-conversion-orders",
    method: "get",
    config: {
      query: { status: statusFilter || undefined, page: 1, page_size: 50 },
    },
  });

  const items = query.data?.data?.items ?? [];
  const total = query.data?.data?.total ?? 0;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Briefcase className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          法务转化订单
        </h1>
        <span className="text-sm text-[var(--color-neutral-500)]">
          共 {total} 单
        </span>
      </div>

      <div className="flex items-center gap-2 bg-white border border-[var(--color-neutral-200)] rounded-lg px-4 py-3">
        <Filter className="w-4 h-4 text-[var(--color-neutral-500)]" />
        <span className="text-sm text-[var(--color-neutral-700)]">状态：</span>
        {[
          ["", "全部"],
          ["pending", "待撮合"],
          ["dispatched", "已派单"],
          ["in_service", "服务中"],
          ["completed", "已完成"],
          ["cancelled", "已取消"],
        ].map(([val, label]) => (
          <button
            key={val}
            type="button"
            onClick={() => setStatusFilter(val as string)}
            className={`px-3 py-1 text-xs rounded transition ${
              statusFilter === val
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-neutral-50)] text-[var(--color-neutral-700)] hover:bg-[var(--color-neutral-100)]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
        {query.isLoading && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            加载中…
          </div>
        )}
        {!query.isLoading && items.length === 0 && (
          <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
            暂无订单
          </div>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-neutral-50)] text-[var(--color-neutral-600)] text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">订单</th>
                <th className="px-4 py-3 text-left">案件</th>
                <th className="px-4 py-3 text-left">服务包</th>
                <th className="px-4 py-3 text-left">报价</th>
                <th className="px-4 py-3 text-left">平台分成</th>
                <th className="px-4 py-3 text-left">律所</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">创建时间</th>
                <th className="px-4 py-3 text-left">文书</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-neutral-100)]">
              {items.map((o) => (
                <tr
                  key={o.id}
                  onClick={() =>
                    go({ to: `/admin/legal-conversion/${o.id}` })
                  }
                  className="hover:bg-[var(--color-neutral-50)] cursor-pointer"
                >
                  <td className="px-4 py-3 font-mono text-xs text-[var(--color-neutral-700)]">
                    #{o.id}
                  </td>
                  <td className="px-4 py-3">案件 #{o.case_id}</td>
                  <td className="px-4 py-3">{o.package_name ?? "—"}</td>
                  <td className="px-4 py-3 font-mono">¥{o.price_quoted}</td>
                  <td className="px-4 py-3 font-mono text-[var(--color-primary)]">
                    ¥{o.platform_fee_amount}
                  </td>
                  <td className="px-4 py-3">
                    {o.assigned_law_firm ? (
                      <span className="text-xs">
                        {o.assigned_law_firm}
                        {o.assigned_lawyer_name && (
                          <span className="text-[var(--color-neutral-500)]">
                            {" "}
                            · {o.assigned_lawyer_name}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-[var(--color-neutral-400)]">未派</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 text-xs rounded ${STATUS_COLOR[o.status]}`}
                    >
                      {STATUS_LABEL[o.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--color-neutral-500)]">
                    {new Date(o.created_at).toLocaleString("zh-CN")}
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => setDocOrderId(o.id)}
                      className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-neutral-300)] text-[var(--color-neutral-700)] rounded hover:bg-[var(--color-neutral-50)]"
                    >
                      <FileText className="w-3 h-3" /> 查看
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {docOrderId !== null && (
        <LegalDocumentModal
          orderId={docOrderId}
          onClose={() => setDocOrderId(null)}
        />
      )}
    </div>
  );
}
