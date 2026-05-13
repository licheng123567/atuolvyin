// 物业法务对接人 — 订单视图（看本租户所有 LegalConversionOrder）
import { Briefcase } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { HelpPanel } from "../../components/ui/HelpPanel";
import { STATUS_LABELS, type OrderStatus } from "./_mock";
import { useLegalOrders } from "./api";
import { OrderDetail } from "./OrderDetail";
import { OrderTable } from "./orderTable";

export function TenantLegalOrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "all">("all");
  const { items: allItems } = useLegalOrders("tenant_legal", {});
  const { items: visibleItems, isLoading } = useLegalOrders(
    "tenant_legal",
    statusFilter === "all" ? {} : { status: statusFilter },
  );

  const counts = {
    pending: allItems.filter((o) => o.status === "pending").length,
    dispatched: allItems.filter((o) => o.status === "dispatched").length,
    in_service: allItems.filter((o) => o.status === "in_service").length,
    completed: allItems.filter((o) => o.status === "completed").length,
  };
  const tenantName = allItems[0]?.tenant_name ?? "本租户";

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Briefcase size={20} style={{ color: "var(--color-primary)" }} />
            <div className="page-title">法务订单（{tenantName}）</div>
          </div>
          <div className="page-subtitle">监督本租户所有转法务订单进度，文书归档</div>
        </div>
      </div>

      <HelpPanel
        tone="info"
        dismissKey="/legal/orders"
        title="物业法务对接人能做什么"
        bullets={[
          <><strong>看：</strong>本租户所有订单（不论是 admin、督导哪个角色创建的）</>,
          <><strong>催：</strong>订单卡在 dispatched / in_service 太久 → 通过站内信催办平台运营或律所</>,
          <><strong>归档：</strong>律师上传的律师函/调解记录/判决书 → 自动同步到此处下载</>,
          <><strong>不能：</strong>编辑订单 / 派律所 / 接单（这些是平台/律所/律师职责）</>,
        ]}
        footer="若本租户内有自己的执业律师，平台运营撮合时可指派到本租户「内置律所」，订单走 Step 3-5 内部流程"
      />

      <div className="status-bar">
        <div className="status-bar-item">待撮合 <strong>{counts.pending}</strong></div>
        <div className="status-bar-item" style={{ color: "var(--color-primary)" }}>已派单 <strong>{counts.dispatched}</strong></div>
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>服务中 <strong>{counts.in_service}</strong></div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>已完成 <strong>{counts.completed}</strong></div>
      </div>

      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {(["all", "pending", "dispatched", "in_service", "completed"] as const).map((v) => (
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
      ) : (
        <OrderTable orders={visibleItems} showFirm showLawyer detailBasePath="/legal/orders" />
      )}
    </div>
  );
}

export function TenantLegalOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <div style={{ padding: 24, maxWidth: 1000 }}>
    <OrderDetail orderId={Number(id)} actor="tenant_legal" backTo="/legal/orders" />
  </div>;
}
