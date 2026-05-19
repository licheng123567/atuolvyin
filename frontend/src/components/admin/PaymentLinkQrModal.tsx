// v2.2 — 缴费链接二维码弹窗：展示支付明细构成 + 二维码 / 短链，供微信发给业主
import { Copy, CreditCard, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";

export interface PaymentBreakdown {
  principal: string | null;
  late_fee: string | null;
  original: string;
  waived: string;
  payable: string;
  has_pending: boolean;
}

interface Props {
  token: string;
  breakdown: PaymentBreakdown;
  sentTo?: string;
  onClose: () => void;
}

function yuan(v: string | null): string {
  if (v == null || v === "") return "—";
  return `¥ ${Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PaymentLinkQrModal({
  token,
  breakdown,
  sentTo,
  onClose,
}: Props) {
  const [copied, setCopied] = useState(false);
  // 缴费链接 = 当前站点的公开账单页（业主扫码 / 点链接都能打开）
  const shareUrl = `${window.location.origin}/pay/${token}`;

  function copy() {
    void navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const row: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 13,
    padding: "3px 0",
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1000 }}>
      <div
        className="ds-modal"
        style={{ maxWidth: 420 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span className="modal-title">
            <CreditCard
              className="inline w-4 h-4 mr-1"
              style={{ verticalAlign: "-3px" }}
            />
            缴费链接
          </span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div
          className="modal-body"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            alignItems: "center",
          }}
        >
          {sentTo && (
            <div style={{ fontSize: 13, color: "#6b7280", textAlign: "center" }}>
              业主 {sentTo} 的缴费链接已生成
            </div>
          )}

          {breakdown.has_pending && (
            <div
              style={{
                background: "#fffbeb",
                color: "#92400e",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 12,
                width: "100%",
              }}
            >
              ⚠ 该案件有待审批减免，当前链接金额按已审批结果计算；减免审批通过后业主刷新链接即见更新。
            </div>
          )}

          {/* 支付明细构成 */}
          <div
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "#f9fafb",
              borderRadius: 6,
            }}
          >
            <div style={row}>
              <span style={{ color: "#6b7280" }}>物业费本金</span>
              <span>{yuan(breakdown.principal)}</span>
            </div>
            <div style={row}>
              <span style={{ color: "#6b7280" }}>违约金 / 滞纳金</span>
              <span>{yuan(breakdown.late_fee)}</span>
            </div>
            <div style={{ ...row, borderTop: "1px solid #e5e7eb", marginTop: 2 }}>
              <span style={{ color: "#6b7280" }}>应缴合计</span>
              <span>{yuan(breakdown.original)}</span>
            </div>
            {Number(breakdown.waived) > 0 && (
              <div style={row}>
                <span style={{ color: "#6b7280" }}>已减免</span>
                <span style={{ color: "#16a34a" }}>- {yuan(breakdown.waived)}</span>
              </div>
            )}
            <div
              style={{
                ...row,
                borderTop: "1px solid #e5e7eb",
                marginTop: 2,
                fontWeight: 700,
              }}
            >
              <span>应支付</span>
              <span style={{ color: "var(--color-primary)" }}>
                {yuan(breakdown.payable)}
              </span>
            </div>
          </div>

          <div
            style={{
              background: "#fff",
              padding: 12,
              borderRadius: 8,
              border: "1px solid var(--color-neutral-200)",
            }}
          >
            <QRCodeSVG value={shareUrl} size={180} level="M" />
          </div>
          <div
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              background: "#f9fafb",
              borderRadius: 6,
            }}
          >
            <span
              style={{
                flex: 1,
                fontFamily: "monospace",
                fontSize: 12,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {shareUrl}
            </span>
            <button
              type="button"
              className="ds-btn ds-btn-ghost ds-btn-sm"
              onClick={copy}
              style={{ padding: "4px 8px" }}
            >
              <Copy className="w-3 h-3" />
              {copied ? "已复制" : "复制链接"}
            </button>
          </div>
          <div
            style={{
              background: "#eff6ff",
              color: "#1e40af",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 12,
              width: "100%",
              textAlign: "center",
            }}
          >
            催收人员可截图二维码或复制链接，通过微信发给业主缴费
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="ds-btn ds-btn-primary" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </div>
  );
}
