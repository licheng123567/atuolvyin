// v0.9.0 — 服务商 admin 系统配置页
//
// 当前仅含一项「N 天未联系自动释放」(与物业 admin 对称)。
// 后续可扩展为通用配置容器(参考 admin/settings/index.tsx 结构)。
//
// 后端:
//   GET /api/v1/provider/settings → ProviderSettingsOut
//   PATCH /api/v1/provider/settings ← ProviderSettingsUpdate
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import { Save, Settings as SettingsIcon, Shield } from "lucide-react";
import { useEffect, useState } from "react";

interface ProviderSettings {
  auto_release_stale_days: number;
}

const DEFAULT: ProviderSettings = {
  auto_release_stale_days: 0,
};

export function ProviderSettingsPage() {
  const invalidate = useInvalidate();
  const { query } = useCustom<ProviderSettings>({
    url: "provider/settings",
    method: "get",
  });
  const remote = query.data?.data;

  const [form, setForm] = useState<ProviderSettings>(DEFAULT);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized) return;
    if (remote) {
      setForm({ ...DEFAULT, ...remote });
      setInitialized(true);
    } else if (!query.isLoading) {
      setForm({ ...DEFAULT });
      setInitialized(true);
    }
  }, [remote, query.isLoading, initialized]);

  const { mutate, mutation } = useCustomMutation();

  const handleSave = () => {
    mutate(
      {
        url: "provider/settings",
        method: "patch",
        values: form,
      },
      {
        onSuccess: () => {
          void invalidate({ resource: "provider/settings", invalidates: ["all"] });
          alert("✓ 配置已保存");
        },
        onError: (err) =>
          alert(`保存失败:${(err as { message?: string }).message ?? "请重试"}`),
      },
    );
  };

  if (!initialized) {
    return <div style={{ padding: 24, color: "#9ca3af" }}>加载中…</div>;
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          服务商系统配置
        </h1>
        <button
          type="button"
          onClick={handleSave}
          disabled={mutation.isPending}
          className="ds-btn ds-btn-primary"
          style={{ marginLeft: "auto" }}
        >
          <Save className="w-3.5 h-3.5" />
          {mutation.isPending ? "保存中…" : "保存配置"}
        </button>
      </div>

      {/* 案件流转配置 */}
      <div
        className="bg-white border border-[var(--color-neutral-200)] rounded-lg"
        style={{ padding: 0 }}
      >
        <div
          className="flex items-center gap-2"
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid var(--color-neutral-100)",
          }}
        >
          <Shield className="w-4 h-4 text-[var(--color-primary)]" />
          <span style={{ fontSize: 14, fontWeight: 600 }}>案件流转</span>
        </div>
        <div style={{ padding: "8px 18px 18px" }}>
          <div className="setting-row">
            <div>
              <div className="setting-label">未联系自动释放公海</div>
              <div className="setting-hint">
                本服务商内催收员手中案件 N 天无业主联系 → 自动释放回
                <strong>服务商内部公海</strong>(同服务商内其他催收员可领)。
                <br />
                <strong>0 = 关闭此功能</strong>;1-180 = 阈值天数。每日 02:00 扫描。
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number"
                className="form-control"
                value={form.auto_release_stale_days}
                min={0}
                max={180}
                style={{ width: 80 }}
                onChange={(e) =>
                  setForm({
                    ...form,
                    auto_release_stale_days: Math.max(
                      0,
                      Math.min(180, Number(e.target.value) || 0),
                    ),
                  })
                }
              />
              <span style={{ fontSize: 13, color: "#374151" }}>
                天 {form.auto_release_stale_days === 0 && "(已关闭)"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProviderSettingsPage;
