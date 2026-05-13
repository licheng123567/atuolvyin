// Sprint 12 — 扫码拨号备份方案
// 当坐席手机不是小米（无 MiPush 通道）时，前端弹二维码，
// 坐席用 App 扫码 → 解析 deeplink → 拉案件信息 → 系统拨号
import { QRCodeSVG } from "qrcode.react";
import { RefreshCw, Smartphone, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

interface QrDialDialogProps {
  qrPayload: string;
  expiresAt: string;
  onClose: () => void;
  onRegenerate: () => void;
}

export function QrDialDialog({
  qrPayload,
  expiresAt,
  onClose,
  onRegenerate,
}: QrDialDialogProps) {
  const expiry = useMemo(() => new Date(expiresAt).getTime(), [expiresAt]);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const remaining = Math.max(0, Math.floor((expiry - now) / 1000));
  const expired = remaining === 0;
  const mm = Math.floor(remaining / 60).toString().padStart(2, "0");
  const ss = (remaining % 60).toString().padStart(2, "0");

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        className="bg-white p-6 w-[560px]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-lg font-semibold">扫码拨号</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-neutral-400)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-[var(--color-neutral-500)] mb-3">
          坐席用「催收 App」扫描下方二维码即可拉起本次案件，自动进入系统拨号界面。
        </p>

        <div className="flex flex-col items-center bg-[var(--color-neutral-50)] py-8 mb-3 rounded">
          {expired ? (
            <div className="w-[360px] h-[360px] flex flex-col items-center justify-center text-[var(--color-neutral-400)]">
              <p className="mb-2 text-sm">二维码已过期</p>
              <button
                type="button"
                onClick={onRegenerate}
                className="flex items-center gap-1 text-sm text-[var(--color-primary)]"
              >
                <RefreshCw className="w-4 h-4" /> 重新生成
              </button>
            </div>
          ) : (
            <QRCodeSVG
              value={qrPayload}
              size={360}
              includeMargin
              level="M"
            />
          )}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span
            className={
              expired
                ? "text-red-600"
                : remaining < 60
                ? "text-[var(--color-warning)]"
                : "text-[var(--color-neutral-500)]"
            }
          >
            {expired ? "已过期" : `剩余 ${mm}:${ss}`}
          </span>
          <button
            type="button"
            onClick={onRegenerate}
            className="text-[var(--color-primary)] flex items-center gap-1"
          >
            <RefreshCw className="w-4 h-4" /> 重新生成
          </button>
        </div>

        <ul className="mt-4 text-xs text-[var(--color-neutral-400)] space-y-1">
          <li>· 二维码 10 分钟内有效，仅可使用一次</li>
          <li>· 适用于华为/OPPO/vivo 等非 MiPush 通道的设备</li>
          <li>· 扫码后 App 自动展示案件信息并跳转系统拨号</li>
        </ul>
      </div>
    </div>
  );
}
