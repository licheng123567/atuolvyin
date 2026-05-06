// 物业管理员 - 系统配置（PRD §3.14 / L2049）
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import { Save, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useState } from "react";

type NotifyChannel = "system" | "sms" | "wechat" | "dingtalk";

interface TenantSettings {
  recording_mode: "live" | "post" | "auto";
  l3_hangup_enabled: boolean;
  contact_freq_max: number;
  retention_days: number;
  notify_quota_warning: boolean;
  notify_script_disabled: boolean;
  notify_work_order_completed: boolean;
  notify_case_escalated: boolean;
  notify_promise_expiring: boolean;
  notify_channels: NotifyChannel[];
}

const NOTIFY_EVENTS: { key: keyof TenantSettings; label: string; hint: string }[] = [
  {
    key: "notify_quota_warning",
    label: "通话配额预警",
    hint: "本月通话分钟用量达 80% / 95% / 100% 时通知管理员",
  },
  {
    key: "notify_script_disabled",
    label: "话术自动禁用",
    hint: "D 级话术（效果差）被系统自动禁用时通知",
  },
  {
    key: "notify_work_order_completed",
    label: "工单处理完成",
    hint: "工单处理员处理完成后通知对应催收员",
  },
  {
    key: "notify_case_escalated",
    label: "大额案件升级",
    hint: "案件升级到主管督导时通知主管",
  },
  {
    key: "notify_promise_expiring",
    label: "承诺日期到期前提醒",
    hint: "业主承诺缴费日临近时通知催收员",
  },
];

const NOTIFY_CHANNELS: { value: NotifyChannel; label: string }[] = [
  { value: "system", label: "站内信" },
  { value: "sms", label: "短信" },
  { value: "wechat", label: "企业微信" },
  { value: "dingtalk", label: "钉钉" },
];

const RECORDING_OPTIONS = [
  { value: "live", label: "实时上传（占带宽）" },
  { value: "post", label: "事后批量上传（省带宽）" },
  { value: "auto", label: "按网络/CPU 自动降级（推荐）" },
];

export function AdminSettingsPage() {
  const invalidate = useInvalidate();
  const { query } = useCustom<TenantSettings>({
    url: "admin/settings",
    method: "get",
  });
  const settings = query.data?.data;

  const [form, setForm] = useState<TenantSettings | null>(null);

  useEffect(() => {
    if (settings && !form) setForm({ ...settings });
  }, [settings, form]);

  const { mutate: patch, mutation } = useCustomMutation();

  const dirty =
    !!form &&
    !!settings &&
    JSON.stringify(form) !== JSON.stringify(settings);

  if (!form) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }

  const save = () => {
    patch(
      {
        url: "admin/settings",
        method: "patch",
        values: form,
      },
      {
        onSuccess: () => {
          invalidate({ resource: "admin/settings", invalidates: ["all"] });
        },
      },
    );
  };

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <SettingsIcon className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">系统配置</h1>
      </div>

      <div
        className="bg-white p-5 border border-[var(--color-neutral-200)] space-y-5"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <Field label="录音模式" hint="决定通话录音如何上传到云端">
          <select
            value={form.recording_mode}
            onChange={(e) =>
              setForm({ ...form, recording_mode: e.target.value as "live" | "post" | "auto" })
            }
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          >
            {RECORDING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="L3 自动挂断"
          hint="检测到 L3 风控（严重违规）时是否自动终止通话。默认关闭"
        >
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.l3_hangup_enabled}
              onChange={(e) =>
                setForm({ ...form, l3_hangup_enabled: e.target.checked })
              }
              className="w-4 h-4"
            />
            {form.l3_hangup_enabled ? "已启用" : "未启用"}
          </label>
        </Field>

        <Field
          label="联系频次上限（每月每户）"
          hint="超出后系统给予提醒；月报中作为合规指标"
        >
          <input
            type="number"
            min={1}
            max={30}
            value={form.contact_freq_max}
            onChange={(e) =>
              setForm({ ...form, contact_freq_max: Number(e.target.value) || 1 })
            }
            className="w-32 px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
          <span className="ml-2 text-sm text-[var(--color-neutral-500)]">次/月</span>
        </Field>

        <Field
          label="数据保留期"
          hint="录音/转写超过该天数后自动归档/删除（30 - 3650 天）"
        >
          <input
            type="number"
            min={30}
            max={3650}
            value={form.retention_days}
            onChange={(e) =>
              setForm({ ...form, retention_days: Number(e.target.value) || 30 })
            }
            className="w-32 px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
          <span className="ml-2 text-sm text-[var(--color-neutral-500)]">天</span>
        </Field>

        <div className="pt-4 border-t border-[var(--color-neutral-100)]">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-2">
            通知规则
          </h2>
          <p className="text-xs text-[var(--color-neutral-500)] mb-3">
            勾选系统在以下事件触发时是否给租户管理员发送通知；下方选择通知渠道
          </p>
          <div className="space-y-2">
            {NOTIFY_EVENTS.map((evt) => (
              <label
                key={evt.key as string}
                className="flex items-start gap-2 text-sm cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={form[evt.key] as boolean}
                  onChange={(e) =>
                    setForm({ ...form, [evt.key]: e.target.checked })
                  }
                  className="mt-1 w-4 h-4"
                />
                <div>
                  <div className="font-medium text-[var(--color-neutral-700)]">
                    {evt.label}
                  </div>
                  <div className="text-xs text-[var(--color-neutral-500)]">
                    {evt.hint}
                  </div>
                </div>
              </label>
            ))}
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-2">
              通知渠道（多选）
            </label>
            <div className="flex flex-wrap gap-3">
              {NOTIFY_CHANNELS.map((ch) => {
                const checked = form.notify_channels.includes(ch.value);
                return (
                  <label
                    key={ch.value}
                    className="inline-flex items-center gap-1.5 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        const set = new Set(form.notify_channels);
                        if (e.target.checked) set.add(ch.value);
                        else set.delete(ch.value);
                        setForm({
                          ...form,
                          notify_channels: Array.from(set) as NotifyChannel[],
                        });
                      }}
                      className="w-4 h-4"
                    />
                    {ch.label}
                  </label>
                );
              })}
            </div>
            {form.notify_channels.length === 0 && (
              <p className="text-xs text-red-600 mt-2">至少选择一个通知渠道</p>
            )}
          </div>
        </div>

        <div className="pt-3 border-t border-[var(--color-neutral-100)]">
          <button
            type="button"
            disabled={
              !dirty || mutation.isPending || form.notify_channels.length === 0
            }
            onClick={save}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Save className="w-4 h-4" />
            {mutation.isPending ? "保存中…" : dirty ? "保存变更" : "无变更"}
          </button>
          <p className="text-xs text-[var(--color-neutral-400)] mt-2">
            其他配置入口：AI 推送灵敏度（在通话工作台内）、风控自定义词（风控关键词）
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
        {label}
      </label>
      {hint && (
        <p className="text-xs text-[var(--color-neutral-500)] mb-2">{hint}</p>
      )}
      {children}
    </div>
  );
}
