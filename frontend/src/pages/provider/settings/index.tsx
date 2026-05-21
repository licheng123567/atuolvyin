// v0.9.0 — 服务商 admin 系统配置页(仅 auto_release_stale_days)
// v1.0.0 — 对齐 TenantSettings 补 3 类 section(录音 / 频次 / 通知)
//
// 后端:
//   GET /api/v1/provider/settings → ProviderSettingsOut
//   PATCH /api/v1/provider/settings ← ProviderSettingsUpdate
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import { Bell, Phone, Save, Settings as SettingsIcon, Shield } from "lucide-react";
import { useEffect, useState } from "react";

type RecordingMode = "live" | "post" | "auto";
type NotifyChannel = "system" | "sms" | "wechat" | "dingtalk";

interface ProviderSettings {
  auto_release_stale_days: number;
  recording_mode: RecordingMode;
  contact_freq_max: number;
  notify_quota_warning: boolean;
  notify_script_disabled: boolean;
  notify_work_order_completed: boolean;
  notify_case_escalated: boolean;
  notify_promise_expiring: boolean;
  notify_channels: NotifyChannel[];
}

const DEFAULT: ProviderSettings = {
  auto_release_stale_days: 0,
  recording_mode: "auto",
  contact_freq_max: 3,
  notify_quota_warning: true,
  notify_script_disabled: true,
  notify_work_order_completed: true,
  notify_case_escalated: true,
  notify_promise_expiring: true,
  notify_channels: ["system"],
};

const RECORDING_OPTIONS: { value: RecordingMode; label: string }[] = [
  { value: "auto", label: "实时优先(自动降级)" },
  { value: "live", label: "仅实时" },
  { value: "post", label: "仅事后" },
];

const NOTIFY_CHANNELS: { value: NotifyChannel; label: string }[] = [
  { value: "system", label: "站内信" },
  { value: "sms", label: "短信" },
  { value: "wechat", label: "微信" },
  { value: "dingtalk", label: "钉钉" },
];

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

  const toggleChannel = (ch: NotifyChannel) => {
    const has = form.notify_channels.includes(ch);
    setForm({
      ...form,
      notify_channels: has
        ? form.notify_channels.filter((c) => c !== ch)
        : [...form.notify_channels, ch],
    });
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

      {/* Section 1: 案件流转 */}
      <SectionCard icon={<Shield className="w-4 h-4 text-[var(--color-primary)]" />} title="案件流转">
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
                  auto_release_stale_days: Math.max(0, Math.min(180, Number(e.target.value) || 0)),
                })
              }
            />
            <span style={{ fontSize: 13, color: "#374151" }}>
              天 {form.auto_release_stale_days === 0 && "(已关闭)"}
            </span>
          </div>
        </div>
      </SectionCard>

      {/* Section 2: 录音模式 */}
      <SectionCard icon={<Phone className="w-4 h-4 text-[var(--color-primary)]" />} title="录音与 AI 配置">
        <div className="setting-row">
          <div>
            <div className="setting-label">录音模式</div>
            <div className="setting-hint">
              live=实时上传(质量高)/ post=事后上传(省流量)/ auto=自动(根据网络降级)
            </div>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            {RECORDING_OPTIONS.map((o) => (
              <label
                key={o.value}
                style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, cursor: "pointer" }}
              >
                <input
                  type="radio"
                  name="recording_mode"
                  value={o.value}
                  checked={form.recording_mode === o.value}
                  onChange={() => setForm({ ...form, recording_mode: o.value })}
                />
                {o.label}
              </label>
            ))}
          </div>
        </div>
      </SectionCard>

      {/* Section 3: 联系频次 */}
      <SectionCard icon={<Phone className="w-4 h-4 text-[var(--color-primary)]" />} title="联系频次控制">
        <div className="setting-row">
          <div>
            <div className="setting-label">同一业主每月拨打上限</div>
            <div className="setting-hint">
              超出后系统锁定该业主拨打按钮;服务商可设比物业更严格的频次
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="number"
              className="form-control"
              value={form.contact_freq_max}
              min={1}
              max={30}
              style={{ width: 80 }}
              onChange={(e) =>
                setForm({
                  ...form,
                  contact_freq_max: Math.max(1, Math.min(30, Number(e.target.value) || 1)),
                })
              }
            />
            <span style={{ fontSize: 13, color: "#374151" }}>次/月</span>
          </div>
        </div>
      </SectionCard>

      {/* Section 4: 通知规则 */}
      <SectionCard icon={<Bell className="w-4 h-4 text-[var(--color-primary)]" />} title="通知规则">
        <NotifyToggle
          label="配额预警通知"
          hint="月度通话配额 80%/95%/100% 时通知"
          value={form.notify_quota_warning}
          onChange={(v) => setForm({ ...form, notify_quota_warning: v })}
        />
        <NotifyToggle
          label="话术失效通知"
          hint="D 级话术自动禁用时通知"
          value={form.notify_script_disabled}
          onChange={(v) => setForm({ ...form, notify_script_disabled: v })}
        />
        <NotifyToggle
          label="工单完成通知"
          hint="工单处理完成时通知催收员"
          value={form.notify_work_order_completed}
          onChange={(v) => setForm({ ...form, notify_work_order_completed: v })}
        />
        <NotifyToggle
          label="案件升级通知"
          hint="大额 / 高风险案件被升级时通知"
          value={form.notify_case_escalated}
          onChange={(v) => setForm({ ...form, notify_case_escalated: v })}
        />
        <NotifyToggle
          label="承诺到期提醒"
          hint="业主承诺缴费日期到期前提醒"
          value={form.notify_promise_expiring}
          onChange={(v) => setForm({ ...form, notify_promise_expiring: v })}
        />

        <div className="setting-row" style={{ flexDirection: "column", alignItems: "stretch" }}>
          <div>
            <div className="setting-label">通知渠道(可多选)</div>
            <div className="setting-hint">至少选择一个;系统会按优先级 站内 → 钉钉 → 微信 → 短信 推送</div>
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
            {NOTIFY_CHANNELS.map((c) => (
              <label
                key={c.value}
                style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  checked={form.notify_channels.includes(c.value)}
                  onChange={() => toggleChannel(c.value)}
                />
                {c.label}
              </label>
            ))}
          </div>
        </div>
      </SectionCard>
    </div>
  );
}

function SectionCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg" style={{ padding: 0 }}>
      <div
        className="flex items-center gap-2"
        style={{ padding: "14px 18px", borderBottom: "1px solid var(--color-neutral-100)" }}
      >
        {icon}
        <span style={{ fontSize: 14, fontWeight: 600 }}>{title}</span>
      </div>
      <div style={{ padding: "8px 18px 18px" }}>{children}</div>
    </div>
  );
}

function NotifyToggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="setting-row">
      <div>
        <div className="setting-label">{label}</div>
        <div className="setting-hint">{hint}</div>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
        />
        {value ? "已开启" : "已关闭"}
      </label>
    </div>
  );
}

export default ProviderSettingsPage;
