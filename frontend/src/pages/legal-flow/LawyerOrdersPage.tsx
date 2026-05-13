// 律师工作台 — 看派给自己的订单 + 上传文书 + 完结
import { useCustom } from "@refinedev/core";
import { Scale } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { HelpPanel } from "../../components/ui/HelpPanel";
import { STATUS_LABELS, type OrderStatus } from "./_mock";
import { useLegalOrders } from "./api";
import { OrderDetail } from "./OrderDetail";
import { OrderTable } from "./orderTable";

interface LawyerContext {
  lawyer_id: number;
  lawyer_name: string;
  specialties: string[];
  law_firm_id: number | null;
  law_firm_name: string | null;
}

export function LawyerOrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "all">("all");
  const { query: ctxQuery } = useCustom<LawyerContext>({
    url: "lawyer/me",
    method: "get",
  });
  const lawyer = ctxQuery.data?.data;
  const { items: allItems } = useLegalOrders("lawyer", {});
  const { items: visibleItems, isLoading, isError } = useLegalOrders(
    "lawyer",
    statusFilter === "all" ? {} : { status: statusFilter },
  );

  const counts = {
    in_service: allItems.filter((o) => o.status === "in_service").length,
    completed: allItems.filter((o) => o.status === "completed").length,
  };

  if (ctxQuery.isError) {
    return (
      <div style={{ padding: 24 }}>
        <div className="ds-card"><div className="card-body" style={{ padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>无律师权限</div>
          <div style={{ fontSize: 13, color: "var(--color-neutral-600)", lineHeight: 1.7 }}>
            当前账号未注册为任何律师（role_in_firm=lawyer + lawyer_id 关联）。请联系律所代表或平台运营。
          </div>
        </div></div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Scale size={20} style={{ color: "var(--color-primary)" }} />
            <div className="page-title">律师工作台（{lawyer?.lawyer_name ?? "—"}）</div>
          </div>
          <div className="page-subtitle">
            {lawyer?.law_firm_name ?? "—"}
            {lawyer?.specialties?.length ? ` · 专长：${lawyer.specialties.join("、")}` : ""}
          </div>
        </div>
      </div>

      <HelpPanel
        tone="tip"
        dismissKey="/lawyer/orders"
        title="律师工作流"
        bullets={[
          <><strong>接单</strong>：律所代表分配后我自动收到通知，状态 in_service</>,
          <><strong>起草</strong>：根据服务包要求生成对应文书 — 律师函 / 调解纪要 / 立案材料 / 判决归档</>,
          <><strong>上传</strong>：在订单详情页点「上传文书」(mock：实际走 MinIO 签名 URL)</>,
          <><strong>完结</strong>：服务交付完成后标记完成</>,
        ]}
        footer="完成订单需要至少 1 份文书；如系自动撤诉/和解类无文书订单，可强制完成（计入审计）"
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>
          进行中 <strong>{counts.in_service}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          本月已结案 <strong>{counts.completed}</strong>
        </div>
      </div>

      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {(["all", "in_service", "completed"] as const).map((v) => (
          <button
            key={v}
            type="button"
            className={`ds-btn ${statusFilter === v ? "ds-btn-primary" : "ds-btn-secondary"} ds-btn-sm`}
            onClick={() => setStatusFilter(v)}
          >
            {v === "all" ? "全部" : STATUS_LABELS[v]}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>加载中…</div>
      ) : isError ? (
        <div style={{ padding: 24, color: "var(--color-danger)" }}>加载失败</div>
      ) : (
        <OrderTable orders={visibleItems} showTenant detailBasePath="/lawyer/orders" />
      )}
    </div>
  );
}

export function LawyerOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <div style={{ padding: 24, maxWidth: 1000 }}>
    <OrderDetail orderId={Number(id)} actor="lawyer" backTo="/lawyer/orders" />
  </div>;
}
