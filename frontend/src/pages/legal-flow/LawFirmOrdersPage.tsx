// 律所代表工作台 — 看派给本所的订单 + 内部分律师
import { Building2 } from "lucide-react";
import { useCustom } from "@refinedev/core";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { HelpPanel } from "../../components/ui/HelpPanel";
import { STATUS_LABELS, type OrderStatus } from "./_mock";
import { useLegalOrders } from "./api";
import { OrderDetail } from "./OrderDetail";
import { OrderTable } from "./orderTable";

interface LawFirmContext {
  law_firm_id: number;
  law_firm_name: string;
  region: string | null;
  rating_avg: number;
  completed_orders: number;
}

export function LawFirmOrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "all">("all");
  const { query: ctxQuery } = useCustom<LawFirmContext>({
    url: "lawfirm/me",
    method: "get",
  });
  const lawFirm = ctxQuery.data?.data;
  const { items: allItems } = useLegalOrders("lawfirm", {});
  const { items: visibleItems, isLoading, isError } = useLegalOrders(
    "lawfirm",
    statusFilter === "all" ? {} : { status: statusFilter },
  );

  const counts = {
    pending_assign: allItems.filter((o) => o.status === "dispatched" && !o.lawyer_id).length,
    in_service: allItems.filter((o) => o.status === "in_service").length,
    completed: allItems.filter((o) => o.status === "completed").length,
  };

  if (ctxQuery.isError) {
    return (
      <div style={{ padding: 24 }}>
        <div className="ds-card"><div className="card-body" style={{ padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>无律所代表权限</div>
          <div style={{ fontSize: 13, color: "var(--color-neutral-600)", lineHeight: 1.7 }}>
            当前账号未注册为任何律所代表（role_in_firm=admin）。请联系平台运营在 law_firm_membership 表中添加记录。
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
            <Building2 size={20} style={{ color: "var(--color-primary)" }} />
            <div className="page-title">律所工作台（{lawFirm?.law_firm_name ?? "—"}）</div>
          </div>
          <div className="page-subtitle">本所被派的订单 — 选律师接单 / 跟进文书 / 完结结算</div>
        </div>
      </div>

      <HelpPanel
        tone="tip"
        dismissKey="/lawfirm/orders"
        title="律所代表能做什么"
        bullets={[
          <><strong>分单</strong>：dispatched 状态订单 → 从本所律师中选承办人 → 状态变 in_service</>,
          <><strong>跟进</strong>：监督本所律师上传文书进度，可催办</>,
          <><strong>完结结算</strong>：律师确认服务完成后标记本订单完结</>,
          <><strong>专长匹配</strong>：分单时显示律师专长（律师函/小额诉讼/调解/物业纠纷），按业务匹配</>,
        ]}
        footer={`律所评分：${lawFirm?.rating_avg ?? "—"} · 累计完成：${lawFirm?.completed_orders ?? 0} 单 · 待分单 ${counts.pending_assign} · 服务中 ${counts.in_service}`}
      />

      <div className="status-bar">
        <div className="status-bar-item" style={{ color: "var(--color-danger)" }}>
          待分律师 <strong>{counts.pending_assign}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-warning)" }}>
          服务中 <strong>{counts.in_service}</strong>
        </div>
        <div className="status-bar-item" style={{ color: "var(--color-success)" }}>
          已完成 <strong>{counts.completed}</strong>
        </div>
      </div>

      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {(["all", "dispatched", "in_service", "completed"] as const).map((v) => (
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
        <OrderTable orders={visibleItems} showTenant showLawyer detailBasePath="/lawfirm/orders" />
      )}
    </div>
  );
}

export function LawFirmOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <div style={{ padding: 24, maxWidth: 1000 }}>
    <OrderDetail orderId={Number(id)} actor="firm_admin" backTo="/lawfirm/orders" />
  </div>;
}
