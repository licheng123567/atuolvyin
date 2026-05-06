// 物业管理员 - 系统配置（PRD §3.14 / L2049）
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import { Save, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useState } from "react";

interface TenantSettings {
  recording_mode: "live" | "post" | "auto";
  l3_hangup_enabled: boolean;
  contact_freq_max: number;
  retention_days: number;
}

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

        <div className="pt-3 border-t border-[var(--color-neutral-100)]">
          <button
            type="button"
            disabled={!dirty || mutation.isPending}
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
