// 法务转化订单详情 — v1.5.7
// admin 点列表行进详情，看到订单全貌 + 关联案件 + 文书 + 状态时间线
import { useCustom } from "@refinedev/core";
import { ArrowLeft, Briefcase, FileText, Scale } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LegalDocumentModal } from "../../../components/legal-conversion/LegalDocumentModal";

interface OrderDetail {
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
  notes: string | null;
}

const STATUS_LABEL: Record<OrderDetail["status"], string> = {
  pending: "待撮合",
  dispatched: "已派单",
  in_service: "服务中",
  completed: "已完成",
  cancelled: "已取消",
};

const STATUS_BADGE: Record<OrderDetail["status"], string> = {
  pending: "ds-badge ds-badge-gray",
  dispatched: "ds-badge ds-badge-blue",
  in_service: "ds-badge ds-badge-orange",
  completed: "ds-badge ds-badge-green",
  cancelled: "ds-badge ds-badge-red",
};

export function AdminLegalConversionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = Number(id);
  const [docOpen, setDocOpen] = useState(false);

  const { query } = useCustom<OrderDetail>({
    url: `admin/legal-conversion-orders/${orderId}`,
    method: "get",
    queryOptions: { enabled: !!orderId },
  });

  const order = query.data?.data;

  return (
    <div style={{ padding: 24, maxWidth: 980 }}>
      <Link
        to="/admin/legal-conversion"
        style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--color-neutral-500)", fontSize: 13.5, textDecoration: "none", marginBottom: 12 }}
      >
        <ArrowLeft className="w-3.5 h-3.5" /> 返回订单列表
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <Briefcase style={{ width: 22, height: 22, color: "var(--color-primary)" }} />
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>法务转化订单 #{orderId}</h1>
        {order && (
          <span className={STATUS_BADGE[order.status]} style={{ fontSize: 12 }}>
            {STATUS_LABEL[order.status]}
          </span>
        )}
      </div>

      {query.isLoading && (
        <div style={{ padding: 32, textAlign: "center", color: "var(--color-neutral-400)" }}>加载中…</div>
      )}

      {query.isError && (
        <div className="ds-card">
          <div className="card-body" style={{ padding: 24 }}>
            <p style={{ color: "var(--color-danger)", marginBottom: 8 }}>订单不存在或已删除</p>
            <p style={{ fontSize: 13, color: "var(--color-neutral-500)" }}>
              请返回列表确认订单号；若是最近创建，可能尚未同步。
            </p>
          </div>
        </div>
      )}

      {order && (
        <>
          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>订单信息</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 24px" }}>
                <Field label="关联案件" value={
                  <Link to={`/admin/cases/${order.case_id}`} style={{ color: "var(--color-primary)" }}>
                    案件 #{order.case_id}
                  </Link>
                } />
                <Field label="服务包" value={order.package_name ?? "—"} />
                <Field label="律所" value={order.assigned_law_firm ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>} />
                <Field label="律师" value={order.assigned_lawyer_name ?? <span style={{ color: "var(--color-neutral-400)" }}>未派</span>} />
                <Field label="报价" value={<span style={{ fontWeight: 600 }}>¥{order.price_quoted}</span>} />
              </div>
            </div>
          </div>

          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-body" style={{ padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>状态时间线</div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13 }}>
                <TimelineItem label="订单创建" time={order.created_at} done />
                <TimelineItem label="律所派单" time={order.dispatched_at} done={!!order.dispatched_at} />
                <TimelineItem label="服务完成" time={order.completed_at} done={!!order.completed_at} />
              </ul>
            </div>
          </div>

          {order.notes && (
            <div className="ds-card" style={{ marginBottom: 16 }}>
              <div className="card-body" style={{ padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>备注</div>
                <div style={{ fontSize: 13, color: "var(--color-neutral-700)", whiteSpace: "pre-wrap" }}>{order.notes}</div>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="ds-btn ds-btn-primary" onClick={() => setDocOpen(true)}>
              <FileText className="w-4 h-4" /> 查看文书
            </button>
            <Link to={`/admin/cases/${order.case_id}`} className="ds-btn ds-btn-secondary">
              <Scale className="w-4 h-4" /> 查看关联案件
            </Link>
          </div>
        </>
      )}

      {docOpen && order && (
        <LegalDocumentModal orderId={order.id} onClose={() => setDocOpen(false)} />
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{value}</div>
    </div>
  );
}

function TimelineItem({ label, time, done }: { label: string; time: string | null; done: boolean }) {
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: done ? "var(--color-success)" : "var(--color-neutral-300)",
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: done ? 500 : 400, color: done ? "#1f2937" : "var(--color-neutral-400)" }}>{label}</span>
      <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-neutral-500)" }}>
        {time ? new Date(time).toLocaleString("zh-CN") : "—"}
      </span>
    </li>
  );
}
