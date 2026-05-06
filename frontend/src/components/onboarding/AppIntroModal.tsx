// Sprint 14.3 — 首次登录 App 下载引导 Modal (PRD §8.2)
import { Smartphone, X } from "lucide-react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useGo } from "@refinedev/core";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

interface AppInfo {
  apk_url: string;
  apk_version: string;
  min_android_version: string;
  notes: string;
}

export function AppIntroModal({
  open,
  onDismiss,
  onPermanentDismiss,
}: {
  open: boolean;
  onDismiss: () => void;
  onPermanentDismiss: () => void;  // 调 PATCH preferences
}) {
  const go = useGo();
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);

  useEffect(() => {
    if (!open || appInfo) return;
    fetch(`${API_BASE}/api/v1/public/app-info`)
      .then((r) => r.json())
      .then((d) => setAppInfo(d as AppInfo))
      .catch(() => setAppInfo(null));
  }, [open, appInfo]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div
        className="bg-white max-w-md w-full"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div className="flex items-center justify-between p-5 border-b border-[var(--color-neutral-200)]">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-[var(--color-primary)]" />
            <h2 className="text-lg font-semibold">需要安装手机 App 才能拨号</h2>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-sm text-[var(--color-neutral-700)]">
            坐席外呼必须通过 Android App 进行（系统限制原因，PC 无法直接发起电话）。
            扫码下载并安装 App，即可在 App 内一键拨打 PC 上的待办案件。
          </p>

          <div className="bg-[var(--color-neutral-50)] rounded p-4 flex flex-col items-center">
            {appInfo ? (
              <>
                <QRCodeSVG value={appInfo.apk_url} size={180} />
                <div className="text-xs text-[var(--color-neutral-500)] mt-2 text-center">
                  v{appInfo.apk_version} · {appInfo.min_android_version}
                </div>
              </>
            ) : (
              <div className="h-[180px] flex items-center text-sm text-[var(--color-neutral-400)]">
                加载下载链接…
              </div>
            )}
          </div>

          {appInfo?.notes && (
            <p className="text-xs text-[var(--color-neutral-500)] leading-relaxed">
              {appInfo.notes}
            </p>
          )}

          <button
            type="button"
            onClick={() => {
              onDismiss();
              go({ to: "/help/app" });
            }}
            className="text-sm text-[var(--color-primary)] hover:underline"
          >
            查看完整安装与使用指南 →
          </button>
        </div>

        <div className="p-5 border-t border-[var(--color-neutral-200)] flex items-center justify-between">
          <label className="inline-flex items-center gap-2 text-sm text-[var(--color-neutral-700)] cursor-pointer">
            <input
              type="checkbox"
              onChange={(e) => {
                if (e.target.checked) onPermanentDismiss();
              }}
              className="w-4 h-4"
            />
            不再提示
          </label>
          <button
            type="button"
            onClick={onDismiss}
            className="px-4 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            知道了
          </button>
        </div>
      </div>
    </div>
  );
}
