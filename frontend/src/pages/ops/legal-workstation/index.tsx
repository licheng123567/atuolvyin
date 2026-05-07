// Sprint 16.2 — 法务工作台（PRD §20.4）— ops 视角，按律所筛选转化订单 + 推动状态
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Briefcase, CheckCircle, FileText, PlayCircle, Receipt, Scale, ShieldQuestion, XCircle } from "lucide-react";
import { useState } from "react";

interface LawFirm {
  id: number;
  name: string;
  region: string | null;
  enabled: boolean;
  accepting_orders: boolean;
  completed_orders: number;
}

interface Order {
  id: number;
  case_id: number;
  package_name: string | null;
  status: string;
  price_quoted: string;
  platform_fee_amount: string;
  assigned_law_firm: string | null;
  assigned_lawyer_name: string | null;
  dispatched_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface FirmStats {
  firm_id: number;
  firm_name: string;
  rating_avg: number;
  completed_orders: number;
  by_status: Record<string, number>;
  platform_fee_total_completed: number;
  platform_fee_unpaid: number;
}

interface Invoice {
  id: number;
  period_start: string;
  period_end: string;
  total_amount: string;
  order_count: number;
  status: "DRAFT" | "CONFIRMED" | "PAID" | "CANCELLED";
  confirmed_at: string | null;
  paid_at: string | null;
}

const INVOICE_STATUS_COLOR: Record<Invoice["status"], string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  CONFIRMED: "bg-amber-100 text-amber-700",
  PAID: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-50 text-red-600",
};
const INVOICE_STATUS_LABEL: Record<Invoice["status"], string> = {
  DRAFT: "草稿",
  CONFIRMED: "已确认",
  PAID: "已付",
  CANCELLED: "已取消",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "待撮合",
  dispatched: "已派单",
  in_service: "服务中",
  completed: "已完成",
  cancelled: "已取消",
};

export function OpsLegalWorkstationPage() {
  const [selectedFirmId, setSelectedFirmId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const firmsQuery = useCustom<{ items: LawFirm[]; total: number }>({
    url: "ops/law-firms",
    method: "get",
    config: { query: { page: 1, page_size: 100 } },
  });

  const ordersQuery = useCustom<{ items: Order[]; total: number }>({
    url: "legal-workstation/orders",
    method: "get",
    config: {
      query: {
        law_firm_id: selectedFirmId ?? undefined,
        status: statusFilter || undefined,
        page: 1,
        page_size: 50,
      },
    },
  });

  const statsQuery = useCustom<FirmStats>({
    url: selectedFirmId
      ? `legal-workstation/firms/${selectedFirmId}/stats`
      : "legal-workstation/firms/0/stats",
    method: "get",
    queryOptions: { enabled: !!selectedFirmId },
  });

  const invoicesQuery = useCustom<{ items: Invoice[]; total: number }>({
    url: selectedFirmId
      ? `legal-workstation/firms/${selectedFirmId}/invoices`
      : "legal-workstation/firms/0/invoices",
    method: "get",
    config: { query: { page: 1, page_size: 20 } },
    queryOptions: { enabled: !!selectedFirmId },
  });

  const { mutate: doStart } = useCustomMutation();
  const { mutate: doInvoiceAction } = useCustomMutation();
  const { mutate: doGenerate } = useCustomMutation();

  const onStart = (id: number) => {
    if (!confirm("启动该订单（dispatched → in_service）？")) return;
    doStart(
      { url: `legal-workstation/orders/${id}/start`, method: "post", values: {} },
      {
        onSuccess: () => ordersQuery.refetch(),
        onError: (err) => alert(`启动失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const onDispatch = (id: number) => {
    if (!selectedFirmId) {
      alert("请先在左侧选中一家律所，再 dispatch 此订单");
      return;
    }
    if (!confirm(`将订单 #${id} 派发给当前律所？`)) return;
    doStart(
      {
        url: `admin/legal-conversion-orders/${id}/dispatch`,
        method: "post",
        values: { law_firm_id: selectedFirmId },
      },
      {
        onSuccess: () => ordersQuery.refetch(),
        onError: (err) => alert(`派单失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const onComplete = (id: number) => {
    const notes = window.prompt("标记完成。可填备注（选填）：", "");
    if (notes === null) return;
    doStart(
      {
        url: `admin/legal-conversion-orders/${id}/complete`,
        method: "post",
        values: { notes: notes.trim() || undefined },
      },
      {
        onSuccess: () => {
          ordersQuery.refetch();
          statsQuery.refetch();
        },
        onError: (err) => alert(`完成失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const onCancelOrder = (id: number) => {
    if (!confirm(`取消订单 #${id}（仅 pending/dispatched 可取消）？`)) return;
    doStart(
      {
        url: `admin/legal-conversion-orders/${id}/cancel`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => ordersQuery.refetch(),
        onError: (err) => alert(`取消失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const firms = firmsQuery.query.data?.data?.items ?? [];
  const orders = ordersQuery.query.data?.data?.items ?? [];
  const stats = statsQuery.query.data?.data;
  const invoices = invoicesQuery.query.data?.data?.items ?? [];

  const onGenerateInvoice = () => {
    if (!selectedFirmId) return;
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const end = new Date(now.getFullYear(), now.getMonth(), 1);
    doGenerate(
      {
        url: `legal-workstation/firms/${selectedFirmId}/invoices`,
        method: "post",
        values: {
          period_start: start.toISOString(),
          period_end: end.toISOString(),
        },
      },
      {
        onSuccess: () => {
          invoicesQuery.refetch();
          statsQuery.refetch();
        },
        onError: (err) => alert(`生成失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  const onInvoiceTransition = (id: number, action: "confirm" | "paid" | "cancel") => {
    const labels = { confirm: "确认账单", paid: "标记已付", cancel: "取消账单" };
    if (!confirm(`${labels[action]}（账单 #${id}）？`)) return;
    doInvoiceAction(
      {
        url: `legal-workstation/invoices/${id}/${action}`,
        method: "post",
        values: {},
      },
      {
        onSuccess: () => {
          invoicesQuery.refetch();
          statsQuery.refetch();
        },
        onError: (err) => alert(`操作失败：${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Scale className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          法务工作台
        </h1>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* 左侧律所列表 */}
        <aside className="col-span-3 bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[var(--color-neutral-100)] text-sm font-semibold">
            律所筛选
          </div>
          <button
            type="button"
            onClick={() => setSelectedFirmId(null)}
            className={`w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--color-neutral-50)] ${
              selectedFirmId === null ? "bg-[var(--color-primary-light)]" : ""
            }`}
          >
            全部律所
          </button>
          {firms.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setSelectedFirmId(f.id)}
              className={`w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--color-neutral-50)] border-t border-[var(--color-neutral-100)] ${
                selectedFirmId === f.id ? "bg-[var(--color-primary-light)]" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span>{f.name}</span>
                <span className="text-xs text-[var(--color-neutral-500)]">
                  {f.completed_orders}
                </span>
              </div>
              {f.region && (
                <div className="text-xs text-[var(--color-neutral-500)]">
                  📍 {f.region}
                </div>
              )}
            </button>
          ))}
        </aside>

        {/* 右侧主区 */}
        <div className="col-span-9 space-y-4">
          {selectedFirmId && stats && (
            <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 grid grid-cols-5 gap-4 text-sm">
              <div>
                <div className="text-xs text-[var(--color-neutral-500)]">律所</div>
                <div className="font-semibold mt-0.5">{stats.firm_name}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--color-neutral-500)]">评分</div>
                <div className="font-semibold mt-0.5">★ {stats.rating_avg}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--color-neutral-500)]">已完成订单</div>
                <div className="font-semibold mt-0.5">{stats.completed_orders}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--color-neutral-500)]">平台分成累计</div>
                <div className="font-semibold mt-0.5 text-[var(--color-primary)]">
                  ¥{stats.platform_fee_total_completed.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-[var(--color-neutral-500)]">应收账款</div>
                <div
                  className={`font-semibold mt-0.5 ${
                    stats.platform_fee_unpaid > 0 ? "text-amber-600" : "text-[var(--color-neutral-700)]"
                  }`}
                >
                  ¥{stats.platform_fee_unpaid.toFixed(2)}
                </div>
              </div>
            </div>
          )}

          {/* Sprint 16.3 — Invoice panel (visible only when a firm is selected) */}
          {selectedFirmId && (
            <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-neutral-100)]">
                <div className="flex items-center gap-2">
                  <Receipt className="w-4 h-4 text-[var(--color-primary)]" />
                  <span className="text-sm font-semibold">介绍费账单</span>
                  <span className="text-xs text-[var(--color-neutral-500)]">
                    ({invoices.length})
                  </span>
                </div>
                <button
                  type="button"
                  onClick={onGenerateInvoice}
                  className="flex items-center gap-1 text-xs px-3 py-1 border border-[var(--color-primary)] text-[var(--color-primary)] rounded hover:bg-[var(--color-primary-light)]"
                >
                  <FileText className="w-3.5 h-3.5" /> 生成上月账单
                </button>
              </div>
              {invoices.length === 0 && (
                <div className="p-6 text-center text-xs text-[var(--color-neutral-500)]">
                  暂无账单
                </div>
              )}
              {invoices.map((inv) => (
                <div
                  key={inv.id}
                  className="px-4 py-3 border-b border-[var(--color-neutral-100)] last:border-0 flex items-center gap-3 text-sm"
                >
                  <span className="font-mono text-xs text-[var(--color-neutral-500)]">
                    #{inv.id}
                  </span>
                  <span className="text-xs text-[var(--color-neutral-700)]">
                    {inv.period_start.slice(0, 10)} ~ {inv.period_end.slice(0, 10)}
                  </span>
                  <span className="font-mono text-[var(--color-primary)]">
                    ¥{inv.total_amount}
                  </span>
                  <span className="text-xs text-[var(--color-neutral-500)]">
                    {inv.order_count} 单
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${INVOICE_STATUS_COLOR[inv.status]}`}
                  >
                    {INVOICE_STATUS_LABEL[inv.status]}
                  </span>
                  <div className="ml-auto flex gap-1">
                    {inv.status === "DRAFT" && (
                      <>
                        <button
                          type="button"
                          onClick={() => onInvoiceTransition(inv.id, "confirm")}
                          className="text-xs px-2 py-1 border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 rounded"
                        >
                          确认
                        </button>
                        <button
                          type="button"
                          onClick={() => onInvoiceTransition(inv.id, "cancel")}
                          className="text-xs px-2 py-1 border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] rounded"
                        >
                          取消
                        </button>
                      </>
                    )}
                    {inv.status === "CONFIRMED" && (
                      <button
                        type="button"
                        onClick={() => onInvoiceTransition(inv.id, "paid")}
                        className="text-xs px-2 py-1 border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 rounded"
                      >
                        标记已付
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg px-4 py-3 flex items-center gap-2">
            <span className="text-sm text-[var(--color-neutral-700)]">状态：</span>
            {[
              ["", "全部"],
              ["dispatched", "已派单"],
              ["in_service", "服务中"],
              ["completed", "已完成"],
            ].map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => setStatusFilter(val as string)}
                className={`px-2.5 py-1 text-xs rounded ${
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
            {orders.length === 0 && !ordersQuery.query.isLoading && (
              <div className="p-12 text-center text-sm text-[var(--color-neutral-500)]">
                <Briefcase className="w-10 h-10 mx-auto text-[var(--color-neutral-300)] mb-2" />
                暂无订单
              </div>
            )}
            {orders.map((o) => (
              <div
                key={o.id}
                className="px-4 py-3 border-b border-[var(--color-neutral-100)] last:border-0 flex items-center gap-4"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-[var(--color-neutral-500)]">
                      #{o.id}
                    </span>
                    <span className="text-sm font-medium">
                      {o.package_name ?? "—"}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-neutral-100)] text-[var(--color-neutral-700)]">
                      {STATUS_LABEL[o.status] ?? o.status}
                    </span>
                  </div>
                  <div className="text-xs text-[var(--color-neutral-600)] mt-0.5">
                    案件 #{o.case_id} · {o.assigned_law_firm ?? "未派"}
                    {o.assigned_lawyer_name && ` · ${o.assigned_lawyer_name}`}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="text-[var(--color-neutral-500)]">报价</div>
                  <div className="font-mono">¥{o.price_quoted}</div>
                </div>
                <div className="text-right text-xs">
                  <div className="text-[var(--color-neutral-500)]">平台</div>
                  <div className="font-mono text-[var(--color-primary)]">
                    ¥{o.platform_fee_amount}
                  </div>
                </div>
                <div className="flex gap-1.5">
                  {o.status === "pending" && (
                    <>
                      <button
                        type="button"
                        onClick={() => onDispatch(o.id)}
                        disabled={!selectedFirmId}
                        title={selectedFirmId ? "派发给当前选中律所" : "先选中律所"}
                        className="flex items-center gap-1 text-xs px-3 py-1.5 border border-amber-400 text-amber-700 bg-amber-50 hover:bg-amber-100 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <ShieldQuestion className="w-3.5 h-3.5" />
                        派单
                      </button>
                      <button
                        type="button"
                        onClick={() => onCancelOrder(o.id)}
                        className="flex items-center gap-1 text-xs px-3 py-1.5 border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] rounded"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        取消
                      </button>
                    </>
                  )}
                  {o.status === "dispatched" && (
                    <>
                      <button
                        type="button"
                        onClick={() => onStart(o.id)}
                        className="flex items-center gap-1 text-xs px-3 py-1.5 border border-[var(--color-primary)] text-[var(--color-primary)] rounded hover:bg-[var(--color-primary-light)]"
                      >
                        <PlayCircle className="w-3.5 h-3.5" />
                        启动服务
                      </button>
                      <button
                        type="button"
                        onClick={() => onCancelOrder(o.id)}
                        className="flex items-center gap-1 text-xs px-3 py-1.5 border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] rounded"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        取消
                      </button>
                    </>
                  )}
                  {o.status === "in_service" && (
                    <button
                      type="button"
                      onClick={() => onComplete(o.id)}
                      className="flex items-center gap-1 text-xs px-3 py-1.5 border border-green-500 text-green-700 bg-green-50 hover:bg-green-100 rounded"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      标记完成
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
