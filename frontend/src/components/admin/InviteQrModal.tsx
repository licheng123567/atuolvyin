// v1.5.5 — 员工首登邀请 modal：二维码 + OTP
import { Copy, KeyRound, Smartphone, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  userName: string;
  phoneFull: string | null;
  phoneMasked: string;
  otp: string | null;
  devMode: boolean;
}

export function InviteQrModal({
  open, onClose, userName, phoneFull, phoneMasked, otp, devMode,
}: Props) {
  const [copied, setCopied] = useState<"phone" | "otp" | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(300);

  useEffect(() => {
    if (!open) return;
    setSecondsLeft(300);
    const id = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [open]);

  if (!open) return null;

  // 二维码内容：员工扫码后跳登录页 + 自动填手机号 + OTP（仅 dev 模式带完整 phone+otp）
  const baseUrl = window.location.origin;
  const qrPayload = devMode && phoneFull && otp
    ? `${baseUrl}/?phone=${phoneFull}&otp=${otp}&first_login=1`
    : `${baseUrl}/`;

  function copyText(text: string, kind: "phone" | "otp") {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(kind);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      style={{ zIndex: 1000 }}
    >
      <div
        className="ds-modal"
        style={{ maxWidth: 480 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <span className="modal-title">
            <KeyRound className="inline w-4 h-4 mr-1" style={{ verticalAlign: "-3px" }} />
            员工首登邀请
          </span>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
          <div style={{ fontSize: 14, color: "#6b7280", textAlign: "center" }}>
            已为「{userName}」生成首次登录凭证
          </div>

          <div style={{ background: "#fff", padding: 12, borderRadius: 8, border: "1px solid var(--color-neutral-200)" }}>
            <QRCodeSVG value={qrPayload} size={160} level="M" />
          </div>

          {devMode ? (
            <>
              <div style={{ fontSize: 12, color: "#9ca3af", textAlign: "center" }}>
                让员工用手机扫码 → 自动跳登录页 + 填好手机号 + OTP
              </div>

              <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#f9fafb", borderRadius: 6 }}>
                  <Smartphone className="w-4 h-4" style={{ color: "#6b7280" }} />
                  <span style={{ fontSize: 13, color: "#6b7280" }}>手机号</span>
                  <span style={{ flex: 1, fontFamily: "monospace", fontSize: 14 }}>{phoneFull ?? phoneMasked}</span>
                  {phoneFull && (
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => copyText(phoneFull, "phone")}
                      style={{ padding: "4px 8px" }}
                    >
                      <Copy className="w-3 h-3" />
                      {copied === "phone" ? "已复制" : "复制"}
                    </button>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#f9fafb", borderRadius: 6 }}>
                  <KeyRound className="w-4 h-4" style={{ color: "#6b7280" }} />
                  <span style={{ fontSize: 13, color: "#6b7280" }}>验证码</span>
                  <span style={{ flex: 1, fontFamily: "monospace", fontSize: 22, fontWeight: 700, letterSpacing: 4, color: "var(--color-primary)" }}>
                    {otp ?? "—"}
                  </span>
                  {otp && (
                    <button
                      type="button"
                      className="ds-btn ds-btn-ghost ds-btn-sm"
                      onClick={() => copyText(otp, "otp")}
                      style={{ padding: "4px 8px" }}
                    >
                      <Copy className="w-3 h-3" />
                      {copied === "otp" ? "已复制" : "复制"}
                    </button>
                  )}
                </div>
              </div>

              <div style={{
                background: "#fffbeb",
                color: "#92400e",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 12,
                width: "100%",
                textAlign: "center",
              }}>
                ⚠️ 开发模式：短信未发出，请将验证码当面或安全渠道转告员工
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: "#374151", textAlign: "center" }}>
              短信验证码已发送至 {phoneMasked}
            </div>
          )}

          <div style={{ fontSize: 12, color: "#6b7280" }}>
            验证码 {Math.floor(secondsLeft / 60)} 分 {secondsLeft % 60} 秒后失效
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
