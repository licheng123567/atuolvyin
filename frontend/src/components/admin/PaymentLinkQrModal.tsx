// v2.2 — 缴费链接二维码弹窗：催收人员可扫码 / 复制短链，通过微信发给业主缴费
import { Copy, CreditCard, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";

interface Props {
  link: string; // H5 缴费链接（二维码内容）
  shortLink: string; // 可复制短链
  sentTo?: string; // 业主掩码手机号
  onClose: () => void;
}

export function PaymentLinkQrModal({ link, shortLink, sentTo, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  function copy() {
    void navigator.clipboard.writeText(shortLink).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

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
          <div
            style={{
              background: "#fff",
              padding: 12,
              borderRadius: 8,
              border: "1px solid var(--color-neutral-200)",
            }}
          >
            <QRCodeSVG value={link} size={180} level="M" />
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
                fontSize: 13,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {shortLink}
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
            催收人员可截图二维码或复制短链，通过微信发给业主缴费
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
