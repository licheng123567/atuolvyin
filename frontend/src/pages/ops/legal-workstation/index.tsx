// Sprint 16.2 — 法务工作台（PRD §20.4）— ops 视角，按律所筛选转化订单 + 推动状态
import { useCustom, useCustomMutation } from "@refinedev/core";
import { Briefcase, PlayCircle, Scale } from "lucide-react";
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
}

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

  const { mutate: doStart } = useCustomMutation();

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

  const firms = firmsQuery.query.data?.data?.items ?? [];
  const orders = ordersQuery.query.data?.data?.items ?? [];
  const stats = statsQuery.query.data?.data;

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
            <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 grid grid-cols-4 gap-4 text-sm">
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
                <div>
                  {o.status === "dispatched" && (
                    <button
                      type="button"
                      onClick={() => onStart(o.id)}
                      className="flex items-center gap-1 text-xs px-3 py-1.5 border border-[var(--color-primary)] text-[var(--color-primary)] rounded hover:bg-[var(--color-primary-light)]"
                    >
                      <PlayCircle className="w-3.5 h-3.5" />
                      启动服务
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
