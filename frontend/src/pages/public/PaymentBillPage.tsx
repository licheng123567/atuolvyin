// v2.2 — 业主公开缴费账单页（无需登录，凭 token 展示账单）
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

interface Breakdown {
  principal: string | null;
  late_fee: string | null;
  original: string;
  waived: string;
  payable: string;
  has_pending: boolean;
}

interface Bill {
  owner_name: string;
  owner_room: string | null;
  payment_mode: string;
  payee_name: string | null;
  payee_account: string | null;
  payee_qr_url: string | null;
  payment_instructions: string | null;
  breakdown: Breakdown;
}

function yuan(v: string | null): string {
  if (v == null) return "—";
  return `¥ ${Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PaymentBillPage() {
  const { token } = useParams<{ token: string }>();
  const [bill, setBill] = useState<Bill | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";
    fetch(`${base}/api/v1/public/payment/${token}`)
      .then(async (resp) => {
        if (resp.status === 410) {
          setError("缴费链接已失效，请联系物业重新获取");
          return;
        }
        if (!resp.ok) {
          setError("缴费链接无效，请联系物业核对");
          return;
        }
        setBill((await resp.json()) as Bill);
      })
      .catch(() => setError("加载失败，请检查网络后重试"))
      .finally(() => setLoading(false));
  }, [token]);

  const wrap: React.CSSProperties = {
    maxWidth: 420,
    margin: "0 auto",
    padding: 16,
    fontFamily: "system-ui, sans-serif",
  };

  if (loading) {
    return <div style={{ ...wrap, textAlign: "center", color: "#6b7280" }}>加载中…</div>;
  }
  if (error || !bill) {
    return (
      <div style={{ ...wrap, textAlign: "center", color: "#b91c1c", paddingTop: 80 }}>
        {error ?? "缴费信息不存在"}
      </div>
    );
  }

  const row: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    padding: "4px 0",
    fontSize: 14,
  };

  return (
    <div style={wrap}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
        {bill.payee_name ?? "物业缴费"}
      </h2>
      <div style={{ color: "#6b7280", fontSize: 14, marginBottom: 16 }}>
        您好，{bill.owner_name}
        {bill.owner_room ? `，房号 ${bill.owner_room}` : ""}
      </div>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 14,
          marginBottom: 16,
        }}
      >
        <div style={row}>
          <span style={{ color: "#6b7280" }}>物业费本金</span>
          <span>{yuan(bill.breakdown.principal)}</span>
        </div>
        <div style={row}>
          <span style={{ color: "#6b7280" }}>违约金 / 滞纳金</span>
          <span>{yuan(bill.breakdown.late_fee)}</span>
        </div>
        <div style={{ ...row, borderTop: "1px solid #e5e7eb" }}>
          <span style={{ color: "#6b7280" }}>应缴合计</span>
          <span>{yuan(bill.breakdown.original)}</span>
        </div>
        {Number(bill.breakdown.waived) > 0 && (
          <div style={row}>
            <span style={{ color: "#6b7280" }}>已减免</span>
            <span style={{ color: "#16a34a" }}>- {yuan(bill.breakdown.waived)}</span>
          </div>
        )}
        <div
          style={{
            ...row,
            borderTop: "1px solid #e5e7eb",
            fontWeight: 700,
            fontSize: 16,
          }}
        >
          <span>应支付</span>
          <span style={{ color: "#2563eb" }}>{yuan(bill.breakdown.payable)}</span>
        </div>
      </div>

      <div style={{ fontSize: 14, lineHeight: 1.7 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>缴费方式</div>
        {bill.payment_instructions && (
          <div style={{ whiteSpace: "pre-wrap", color: "#374151" }}>
            {bill.payment_instructions}
          </div>
        )}
        {bill.payee_account && (
          <div style={{ color: "#374151" }}>收款账户：{bill.payee_account}</div>
        )}
        {bill.payee_name && (
          <div style={{ color: "#374151" }}>收款户名：{bill.payee_name}</div>
        )}
        {bill.payee_qr_url && (
          <img
            src={bill.payee_qr_url}
            alt="收款码"
            style={{ width: 180, height: 180, objectFit: "contain", marginTop: 8 }}
          />
        )}
      </div>

      <div
        style={{
          marginTop: 20,
          paddingTop: 12,
          borderTop: "1px dashed #e5e7eb",
          fontSize: 12,
          color: "#9ca3af",
          textAlign: "center",
        }}
      >
        —— v1.1 上线后可在此直接扫码支付 ——
      </div>
    </div>
  );
}
