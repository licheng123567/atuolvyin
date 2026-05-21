// 1:1 还原 ui/admin.html#a-settings 系统配置
import {
  useCreate,
  useCustom,
  useCustomMutation,
  useDelete,
  useInvalidate,
  useList,
} from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PaginatedResponse } from "../../../types";

interface SuggestionConfig {
  sensitivity: number; // 1-5
  max_per_push: number; // 1-10
}

type RecordingMode = "live" | "post" | "auto";
type NotifyChannel = "system" | "sms" | "wechat" | "dingtalk";

interface TenantSettings {
  recording_mode: RecordingMode;
  l3_hangup_enabled: boolean;
  contact_freq_max: number;
  retention_days: number;
  // v1.6 — 本金打折审批策略
  discount_auto_approve_threshold_pct: number;
  discount_supervisor_max_pct: number;
  discount_disabled: boolean;
  // v1.6.2 — 滞纳金减免独立策略
  late_fee_waive_auto_approve_threshold_pct: number;
  late_fee_waive_supervisor_max_pct: number;
  late_fee_waive_disabled: boolean;
  notify_quota_warning: boolean;
  notify_script_disabled: boolean;
  notify_work_order_completed: boolean;
  notify_case_escalated: boolean;
  notify_promise_expiring: boolean;
  notify_channels: NotifyChannel[];
  // v0.9.0 — N 天未联系自动释放公海(0 = 关闭)
  auto_release_stale_days: number;
}

interface RiskKeyword {
  id: number;
  tenant_id: number | null;
  category: string;
  speaker: string;
  level: string;
  keyword: string;
  is_active: boolean;
}

const RECORDING_OPTIONS: { value: RecordingMode; label: string }[] = [
  { value: "auto", label: "实时优先（自动降级）" },
  { value: "live", label: "仅实时" },
  { value: "post", label: "仅事后" },
];

const SENSITIVITY_LABELS: Record<number, string> = {
  1: "低（保守）",
  3: "中",
  5: "高（积极）",
};

const DEFAULT_TENANT_SETTINGS: TenantSettings = {
  recording_mode: "auto",
  l3_hangup_enabled: false,
  contact_freq_max: 3,
  retention_days: 365,
  discount_auto_approve_threshold_pct: 10,
  discount_supervisor_max_pct: 30,
  discount_disabled: false,
  late_fee_waive_auto_approve_threshold_pct: 50,
  late_fee_waive_supervisor_max_pct: 100,
  late_fee_waive_disabled: false,
  notify_quota_warning: true,
  notify_script_disabled: true,
  notify_work_order_completed: true,
  notify_case_escalated: true,
  notify_promise_expiring: true,
  notify_channels: ["system"],
  auto_release_stale_days: 0,
};

export function AdminSettingsPage() {
  const invalidate = useInvalidate();

  // ── tenant settings ─────────────────────────
  const { query } = useCustom<TenantSettings>({
    url: "admin/settings",
    method: "get",
  });
  const settings = query.data?.data;

  // ── suggestion config ───────────────────────
  const { query: suggestQuery } = useCustom<SuggestionConfig>({
    url: "admin/suggestion-config",
    method: "get",
  });
  const suggestion = suggestQuery.data?.data;

  // ── custom risk keywords (tenant-specific only) ──
  const kwFilters: CrudFilter[] = [
    { field: "is_active", operator: "eq", value: true },
  ];
  const { query: kwQuery } = useList<RiskKeyword>({
    resource: "admin/risk-keywords",
    filters: kwFilters,
    pagination: { currentPage: 1, pageSize: 100 },
  });
  const kwData = kwQuery.data?.data as unknown as
    | PaginatedResponse<RiskKeyword>
    | undefined;
  const customKeywords = (kwData?.items ?? []).filter(
    (k) => k.tenant_id !== null,
  );

  const [form, setForm] = useState<TenantSettings | null>(null);
  const [suggestForm, setSuggestForm] = useState<SuggestionConfig | null>(null);
  const [kwInput, setKwInput] = useState("");
  const formInitRef = useRef(false);
  const suggestInitRef = useRef(false);

  useEffect(() => {
    // 初始化策略：拿到 settings 立即初始化；查询完成（无论成功失败）也要初始化以避免一直「加载中」
    if (formInitRef.current) return;
    if (settings) {
      formInitRef.current = true;
      setForm({
        ...DEFAULT_TENANT_SETTINGS,
        ...settings,
        notify_channels: settings.notify_channels ?? ["system"],
      });
    } else if (!query.isLoading) {
      // 查询失败（如 401/403/500）：用前端默认值初始化，让用户至少能编辑
      formInitRef.current = true;
      setForm({ ...DEFAULT_TENANT_SETTINGS });
    }
  }, [settings, query.isLoading]);

  // 兜底：3 秒内如果还没初始化（无论原因），用默认值初始化避免页面永久卡死
  useEffect(() => {
    const t = setTimeout(() => {
      if (!formInitRef.current) {
        formInitRef.current = true;
        setForm({ ...DEFAULT_TENANT_SETTINGS });
      }
    }, 3000);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (suggestion && !suggestInitRef.current) {
      suggestInitRef.current = true;
      setSuggestForm({ ...suggestion });
    }
  }, [suggestion]);

  const { mutate: patchSettings, mutation: settingsMut } = useCustomMutation();
  const { mutate: putSuggest, mutation: suggestMut } = useCustomMutation();
  const { mutate: createKw } = useCreate();
  const { mutate: delKw } = useDelete();

  const dirty =
    !!form &&
    !!settings &&
    JSON.stringify(form) !== JSON.stringify(settings);
  const suggestDirty =
    !!suggestForm &&
    !!suggestion &&
    JSON.stringify(suggestForm) !== JSON.stringify(suggestion);
  const anyDirty = dirty || suggestDirty;

  if (!form) {
    return (
      <div style={{ padding: 24, color: "var(--color-neutral-400)" }}>
        加载中…
      </div>
    );
  }

  const saveAll = () => {
    if (dirty) {
      patchSettings(
        { url: "admin/settings", method: "patch", values: form },
        {
          onSuccess: () =>
            invalidate({ resource: "admin/settings", invalidates: ["all"] }),
        },
      );
    }
    if (suggestDirty && suggestForm) {
      putSuggest(
        { url: "admin/suggestion-config", method: "put", values: suggestForm },
        {
          onSuccess: () =>
            invalidate({
              resource: "admin/suggestion-config",
              invalidates: ["all"],
            }),
        },
      );
    }
  };

  const addKeyword = () => {
    const word = kwInput.trim();
    if (!word) return;
    createKw(
      {
        resource: "admin/risk-keywords",
        values: {
          category: "custom",
          speaker: "callee",
          level: "L1",
          keyword: word,
        },
      },
      {
        onSuccess: () => {
          setKwInput("");
          kwQuery.refetch();
        },
      },
    );
  };

  const removeKeyword = (id: number) => {
    delKw(
      { resource: "admin/risk-keywords", id },
      { onSuccess: () => kwQuery.refetch() },
    );
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">系统配置</h1>
        </div>
      </div>

      {/* ─── §1 录音与 AI 配置 ─── */}
      <div className="config-section">
        <div className="config-section-title">🎙️ 录音与 AI 配置</div>

        <div className="setting-row">
          <div>
            <div className="setting-label">录音上传模式</div>
            <div className="setting-hint">
              实时优先：优先使用实时推流，网络差时自动降级为事后上传
            </div>
          </div>
          <div className="radio-group">
            {RECORDING_OPTIONS.map((o) => (
              <label key={o.value} className="radio-option">
                <input
                  type="radio"
                  name="record_mode"
                  checked={form.recording_mode === o.value}
                  onChange={() =>
                    setForm({ ...form, recording_mode: o.value })
                  }
                />
                {o.label}
              </label>
            ))}
          </div>
        </div>

        <div className="setting-row">
          <div>
            <div className="setting-label">L3 风险自动挂断</div>
            <div className="setting-hint" style={{ color: "#d97706" }}>
              ⚠️ 默认关闭。开启后，当检测到 L3 级风险词（如严重威胁）时将自动挂断通话，请谨慎开启。
            </div>
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={form.l3_hangup_enabled}
              onChange={(e) =>
                setForm({ ...form, l3_hangup_enabled: e.target.checked })
              }
            />
            <div className="toggle-track">
              <div className="toggle-thumb" />
            </div>
            <span style={{ fontSize: 13, color: "#374151" }}>
              {form.l3_hangup_enabled ? "已开启" : "已关闭"}
            </span>
          </label>
        </div>

        <div className="setting-row">
          <div>
            <div className="setting-label">AI 话术推送灵敏度</div>
            <div className="setting-hint">
              灵敏度越高，AI 推送话术越频繁；建议设为「中」以平衡质量与干扰
            </div>
          </div>
          <div className="radio-group">
            {[1, 3, 5].map((v) => (
              <label key={v} className="radio-option">
                <input
                  type="radio"
                  name="sensitivity"
                  checked={(suggestForm?.sensitivity ?? 3) === v}
                  onChange={() =>
                    setSuggestForm((prev) =>
                      prev ? { ...prev, sensitivity: v } : prev,
                    )
                  }
                  disabled={!suggestForm}
                />
                {SENSITIVITY_LABELS[v]}
              </label>
            ))}
          </div>
        </div>

        <div className="setting-row">
          <div>
            <div className="setting-label">单次最多推送话术数</div>
            <div className="setting-hint">每次异议识别后最多推送的话术卡片数量</div>
          </div>
          <select
            className="form-control"
            style={{ width: 100 }}
            value={suggestForm?.max_per_push ?? 3}
            onChange={(e) =>
              setSuggestForm((prev) =>
                prev
                  ? { ...prev, max_per_push: Number(e.target.value) || 1 }
                  : prev,
              )
            }
            disabled={!suggestForm}
          >
            {[1, 2, 3, 5].map((v) => (
              <option key={v} value={v}>
                {v}条
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ─── §2 联系频次控制 ─── */}
      <div className="config-section">
        <div className="config-section-title">📞 联系频次控制</div>

        <div className="setting-row">
          <div>
            <div className="setting-label">同一业主每月拨打上限</div>
            <div className="setting-hint">
              超出后系统锁定该业主的拨打按钮，直至下月自动解锁
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
                  contact_freq_max: Number(e.target.value) || 1,
                })
              }
            />
            <span style={{ fontSize: 13, color: "#374151" }}>次/月</span>
          </div>
        </div>

        <div className="setting-row">
          <div>
            <div className="setting-label">同一业主每日拨打上限</div>
            <div className="setting-hint">v1.1 上线，敬请期待</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="number"
              className="form-control"
              value={2}
              disabled
              style={{ width: 80 }}
            />
            <span style={{ fontSize: 13, color: "#374151" }}>次/天</span>
          </div>
        </div>

        {/* v0.9.0 — N 天未联系自动释放公海 */}
        <div className="setting-row">
          <div>
            <div className="setting-label">未联系自动释放公海</div>
            <div className="setting-hint">
              催收员手中案件 N 天无业主联系 → 自动释放回物业公海(可重新分配)。
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

        <div className="setting-row">
          <div>
            <div className="setting-label">两次联系最短间隔</div>
            <div className="setting-hint">v1.1 上线，敬请期待</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="number"
              className="form-control"
              value={24}
              disabled
              style={{ width: 80 }}
            />
            <span style={{ fontSize: 13, color: "#374151" }}>小时</span>
          </div>
        </div>
      </div>

      {/* ─── §2.5 协商打折 / 减免审批策略 (v1.6 / v1.6.2) ─── */}
      <div className="config-section">
        <div className="config-section-title">💰 减免审批策略（本金打折 + 滞纳金减免）</div>
        <div className="form-hint" style={{ marginBottom: 12 }}>
          多数物业愿意减免滞纳金以换取本金回收，但本金打折通常严格管控。两类策略可独立设置。
        </div>

        {/* 本金打折策略 */}
        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 6, padding: 12, marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#7c2d12", marginBottom: 8 }}>
            💴 本金打折策略
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">是否启用本金打折</div>
              <div className="setting-hint">停用后无法发起本金打折申请</div>
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={!form.discount_disabled}
                onChange={(e) =>
                  setForm({ ...form, discount_disabled: !e.target.checked })
                }
                style={{ width: 16, height: 16 }}
              />
              <span style={{ fontSize: 13, color: form.discount_disabled ? "var(--color-danger)" : "var(--color-success)" }}>
                {form.discount_disabled ? "已停用" : "已启用"}
              </span>
            </label>
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">自动批准阈值</div>
              <div className="setting-hint">折扣 &lt; X% 系统直接批准；设为 0 表示任何打折都需人工审批</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number"
                className="form-control"
                value={form.discount_auto_approve_threshold_pct}
                min={0}
                max={100}
                style={{ width: 80 }}
                disabled={form.discount_disabled}
                onChange={(e) =>
                  setForm({
                    ...form,
                    discount_auto_approve_threshold_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                  })
                }
              />
              <span style={{ fontSize: 13, color: "#374151" }}>%</span>
            </div>
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">督导审批上限</div>
              <div className="setting-hint">折扣 ≤ X% 督导可批；&gt; X% 转物业管理员。一般物业建议 30%</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number"
                className="form-control"
                value={form.discount_supervisor_max_pct}
                min={form.discount_auto_approve_threshold_pct}
                max={100}
                style={{ width: 80 }}
                disabled={form.discount_disabled}
                onChange={(e) =>
                  setForm({
                    ...form,
                    discount_supervisor_max_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                  })
                }
              />
              <span style={{ fontSize: 13, color: "#374151" }}>%</span>
            </div>
          </div>

          {!form.discount_disabled && (
            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 6, padding: 10, marginTop: 4, fontSize: 12.5, color: "#166534", lineHeight: 1.7 }}>
              <strong>规则</strong>：
              {form.discount_auto_approve_threshold_pct === 0 ? (
                <>本金打折申请都需人工审批。</>
              ) : (
                <>催收员可独立打折 0–{form.discount_auto_approve_threshold_pct - 1}%；</>
              )}
              督导可批 {form.discount_auto_approve_threshold_pct}–{form.discount_supervisor_max_pct}%；&gt; {form.discount_supervisor_max_pct}% 转物业管理员
            </div>
          )}
        </div>

        {/* 滞纳金减免策略 */}
        <div style={{ background: "#ecfeff", border: "1px solid #a5f3fc", borderRadius: 6, padding: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#0e7490", marginBottom: 8 }}>
            ⏰ 滞纳金减免策略
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">是否启用滞纳金减免</div>
              <div className="setting-hint">多数物业愿意全部减免滞纳金以换取本金回收</div>
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={!form.late_fee_waive_disabled}
                onChange={(e) =>
                  setForm({ ...form, late_fee_waive_disabled: !e.target.checked })
                }
                style={{ width: 16, height: 16 }}
              />
              <span style={{ fontSize: 13, color: form.late_fee_waive_disabled ? "var(--color-danger)" : "var(--color-success)" }}>
                {form.late_fee_waive_disabled ? "已停用" : "已启用"}
              </span>
            </label>
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">自动批准阈值</div>
              <div className="setting-hint">滞纳金减免 &lt; X% 自动批准；默认 50% 较为宽松</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number"
                className="form-control"
                value={form.late_fee_waive_auto_approve_threshold_pct}
                min={0}
                max={100}
                style={{ width: 80 }}
                disabled={form.late_fee_waive_disabled}
                onChange={(e) =>
                  setForm({
                    ...form,
                    late_fee_waive_auto_approve_threshold_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                  })
                }
              />
              <span style={{ fontSize: 13, color: "#374151" }}>%</span>
            </div>
          </div>

          <div className="setting-row">
            <div>
              <div className="setting-label">督导审批上限</div>
              <div className="setting-hint">滞纳金减免 ≤ X% 督导可批；默认 100%（即可全部减免）</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="number"
                className="form-control"
                value={form.late_fee_waive_supervisor_max_pct}
                min={form.late_fee_waive_auto_approve_threshold_pct}
                max={100}
                style={{ width: 80 }}
                disabled={form.late_fee_waive_disabled}
                onChange={(e) =>
                  setForm({
                    ...form,
                    late_fee_waive_supervisor_max_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                  })
                }
              />
              <span style={{ fontSize: 13, color: "#374151" }}>%</span>
            </div>
          </div>

          {!form.late_fee_waive_disabled && (
            <div style={{ background: "#f0fdfa", border: "1px solid #99f6e4", borderRadius: 6, padding: 10, marginTop: 4, fontSize: 12.5, color: "#0f766e", lineHeight: 1.7 }}>
              <strong>规则</strong>：催收员可独立减免 0–{Math.max(0, form.late_fee_waive_auto_approve_threshold_pct - 1)}%；
              督导可批 {form.late_fee_waive_auto_approve_threshold_pct}–{form.late_fee_waive_supervisor_max_pct}%；
              &gt; {form.late_fee_waive_supervisor_max_pct}% 转物业管理员
            </div>
          )}
        </div>
      </div>

      {/* ─── §3 自定义风控关键词 ─── */}
      <div className="config-section">
        <div className="config-section-title">
          🚨 自定义风控关键词（在全局词库基础上叠加）
        </div>
        <div className="form-hint" style={{ marginBottom: 10 }}>
          以下关键词仅对本公司生效，优先级低于平台全局词库
        </div>
        <div className="tag-input-wrap">
          {customKeywords.map((k) => (
            <span key={k.id} className="keyword-tag">
              {k.keyword}
              <span className="remove" onClick={() => removeKeyword(k.id)}>
                ×
              </span>
            </span>
          ))}
          <input
            type="text"
            placeholder="输入关键词后按回车添加"
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addKeyword();
              }
            }}
            style={{
              border: "none",
              outline: "none",
              fontSize: 13,
              minWidth: 150,
              padding: "2px 4px",
            }}
          />
        </div>
      </div>

      {/* ─── §4 数据保留策略（只读）─── */}
      <div className="config-section">
        <div className="config-section-title">
          📁 数据保留策略（只读，v2.0 执行）
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}
        >
          <div
            style={{
              padding: 12,
              background: "#f9fafb",
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#6b7280" }}>录音文件：</span>
            <strong>{form.retention_days >= 30 ? Math.round(form.retention_days / 30) : form.retention_days} 个月</strong>
          </div>
          <div
            style={{
              padding: 12,
              background: "#f9fafb",
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#6b7280" }}>转写文本：</span>
            <strong>24 个月</strong>
          </div>
          <div
            style={{
              padding: 12,
              background: "#f9fafb",
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#6b7280" }}>案件数据：</span>
            <strong>法定期限</strong>
          </div>
          <div
            style={{
              padding: 12,
              background: "#f9fafb",
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#6b7280" }}>审计日志：</span>
            <strong>永久保留</strong>
          </div>
        </div>
        <div
          style={{
            fontSize: 12,
            color: "#9ca3af",
            marginTop: 10,
            fontStyle: "italic",
          }}
        >
          具体删除执行由平台运维负责（v2.0 版本实现）
        </div>
      </div>

      {/* ─── 保存按钮 ─── */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          className="ds-btn ds-btn-primary"
          disabled={!anyDirty || settingsMut.isPending || suggestMut.isPending}
          onClick={saveAll}
        >
          <Save className="w-3.5 h-3.5" />
          {settingsMut.isPending || suggestMut.isPending
            ? "保存中…"
            : "保存配置"}
        </button>
      </div>
    </div>
  );
}
