// v1.9.0 + v1.9.1 — 法务订单内部处理详情页
// 三栏：左 业主信息 / 中 actions 时间线 + 附件 / 右 sticky 操作按钮组
// v1.9.1 — 律师函起草 Wizard / 承诺到期重新打开 / 盖章版 PDF 上传
import { useCustom, useCustomMutation } from "@refinedev/core";
import {
  AlertCircle, ArrowLeft, CheckCircle2, FileText, Gavel, Handshake, Lightbulb,
  Mail, MessageCircle, Paperclip, Printer, RotateCcw, ShieldAlert, Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

interface ActionOut {
  id: number;
  action_type: string;
  actor_name: string | null;
  occurred_at: string;
  note: string | null;
  letter_template_name: string | null;
  partner_law_firm_name: string | null;
  attachment_filename: string | null;
  attachment_key: string | null;
  letter_variables: Record<string, string> | null;
}

interface InternalOrderDetail {
  id: number;
  case_id: number;
  status: string;
  owner_name: string;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  amount_owed: string | number | null;
  months_overdue: number | null;
  arrears_reason: string | null;
  project_name: string | null;
  notes: string | null;
  created_at: string;
  actions: ActionOut[];
  internal_close_reason: string | null;
  internal_closed_at: string | null;
  promise_due_date: string | null;
}

interface LetterTemplate {
  id: number;
  name: string;
  category: string;
  body_md: string;
  variables: { name: string; label: string; type?: string; required?: boolean }[] | null;
}

const ACTION_META: Record<string, { label: string; icon: React.ReactNode; cls: string }> = {
  contact_owner:      { label: "法务沟通", icon: <MessageCircle size={14} />, cls: "tl-call" },
  send_lawyer_letter: { label: "出具律师函", icon: <Mail size={14} />,         cls: "tl-system" },
  send_notice:        { label: "出具催告函", icon: <Mail size={14} />,         cls: "tl-system" },
  mediation:          { label: "调解会议",   icon: <Handshake size={14} />,    cls: "tl-system" },
  other:              { label: "备注",       icon: <FileText size={14} />,     cls: "tl-system" },
};

const CLOSE_REASON_LABEL: Record<string, string> = {
  paid: "已缴清",
  promised: "达成承诺",
  uncollectible: "无法催收",
  escalated: "升级到律所",
};

// 系统已知字段：从订单上下文自动填入
const KNOWN_VARS = new Set([
  "owner_name", "building", "room", "amount_owed", "months", "property_company",
]);

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function isOverdue(dueDate: string | null): boolean {
  if (!dueDate) return false;
  return dueDate < todayISO();
}

// v1.9.2 — 欠费分级处理建议（< 3k 催告 / 3k-1万 律师函 / > 1万 升级律所）
function getProcessingSuggestion(amount: number | null): { tier: "notice" | "letter" | "escalate"; text: string; color: string } | null {
  if (amount == null || amount <= 0) return null;
  if (amount < 3000) {
    return { tier: "notice", text: `本案欠费 ¥${amount.toLocaleString("zh-CN")}（< ¥3,000），建议先出催告函 + 电话沟通，避免过度施压`, color: "#16a34a" };
  }
  if (amount <= 10000) {
    return { tier: "letter", text: `本案欠费 ¥${amount.toLocaleString("zh-CN")}（¥3k-1万），建议出律师函 + 调解，多数案件可在内部解决`, color: "#ea580c" };
  }
  return { tier: "escalate", text: `本案欠费 ¥${amount.toLocaleString("zh-CN")}（> ¥10,000），建议律师函震慑后若 7 日无响应直接升级律所走诉讼`, color: "#dc2626" };
}

export function LegalInternalOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { query } = useCustom<InternalOrderDetail>({
    url: `legal/internal-orders/${id}`,
    method: "get",
  });
  const isLoading = query.isLoading;
  const order = query.data?.data;
  const refetch = query.refetch;
  const isClosed = order && order.status !== "internal_processing";
  const isClosedPromised = order?.status === "closed_promised";
  const overdue = isClosedPromised && isOverdue(order?.promise_due_date ?? null);

  const { mutate: createAction } = useCustomMutation();
  const { mutate: closeOrder } = useCustomMutation();
  const { mutate: escalate } = useCustomMutation();
  const { mutate: reopen } = useCustomMutation();

  // 普通 action（contact_owner / mediation / other）
  const [simpleType, setSimpleType] = useState<string | null>(null);
  const [simpleNote, setSimpleNote] = useState("");

  // Wizard：律师函/催告函起草
  const [wizardType, setWizardType] = useState<"send_lawyer_letter" | "send_notice" | null>(null);
  const [wizardStep, setWizardStep] = useState<0 | 1 | 2>(0);
  const [wizardTemplateId, setWizardTemplateId] = useState<number | null>(null);
  const [wizardFirmId, setWizardFirmId] = useState<number | null>(null);
  const [wizardVars, setWizardVars] = useState<Record<string, string>>({});
  const [wizardNote, setWizardNote] = useState("");

  // 关闭表单
  const [closeReason, setCloseReason] = useState<string | null>(null);
  const [closeNote, setCloseNote] = useState("");
  const [promiseDate, setPromiseDate] = useState<string>("");

  // 附件上传：当前正在上传的 action
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingActionId, setUploadingActionId] = useState<number | null>(null);

  // 模板/律所候选（Wizard 用）
  const { query: templatesQuery } = useCustom<{ items: LetterTemplate[] }>({
    url: "admin/internal-letter-templates",
    method: "get",
    config: { query: { only_active: true, page_size: 100 } },
    queryOptions: { enabled: wizardType !== null },
  });
  const { query: firmsQuery } = useCustom<{ items: { id: number; name: string }[] }>({
    url: "admin/partner-law-firms",
    method: "get",
    config: { query: { only_active: true, page_size: 100 } },
    queryOptions: { enabled: wizardType === "send_lawyer_letter" },
  });
  const templates = templatesQuery.data?.data?.items ?? [];
  const firms = firmsQuery.data?.data?.items ?? [];
  const wizardTpl = useMemo(
    () => templates.find((t) => t.id === wizardTemplateId) ?? null,
    [templates, wizardTemplateId],
  );

  // 自动填充已知变量（每次模板切换/订单加载时）
  function autofillVars(tpl: LetterTemplate | null) {
    if (!tpl || !order) return;
    const filled: Record<string, string> = {};
    for (const v of (tpl.variables ?? [])) {
      const k = v.name;
      if (k === "owner_name") filled[k] = order.owner_name;
      else if (k === "building") filled[k] = order.building ?? "";
      else if (k === "room") filled[k] = order.room ?? "";
      else if (k === "amount_owed") filled[k] = order.amount_owed != null ? String(order.amount_owed) : "";
      else if (k === "months") filled[k] = order.months_overdue != null ? String(order.months_overdue) : "";
      else if (k === "property_company") filled[k] = order.project_name ?? "";
      else if (k === "notice_date") filled[k] = todayISO();
      else filled[k] = wizardVars[k] ?? "";
    }
    setWizardVars(filled);
  }

  // 渲染模板 body：把 {{var}} 替换为实际值
  function renderTemplate(tpl: LetterTemplate, vars: Record<string, string>): string {
    return tpl.body_md.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
  }

  if (isLoading) return <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>加载中…</div>;
  if (!order) return <div style={{ padding: 32, color: "var(--color-danger)" }}>订单不存在</div>;

  const room = (order.building || "") + (order.room || "") || "—";
  const amount = order.amount_owed != null ? Number(order.amount_owed).toLocaleString("zh-CN") : "—";

  function resetSimple() { setSimpleType(null); setSimpleNote(""); }
  function resetWizard() {
    setWizardType(null);
    setWizardStep(0);
    setWizardTemplateId(null);
    setWizardFirmId(null);
    setWizardVars({});
    setWizardNote("");
  }
  function resetClose() { setCloseReason(null); setCloseNote(""); setPromiseDate(""); }

  function submitSimple() {
    if (!simpleType) return;
    createAction(
      {
        url: `legal/internal-orders/${id}/actions`,
        method: "post",
        values: { action_type: simpleType, note: simpleNote || undefined },
      },
      {
        onSuccess: () => { alert("✓ 已记录"); resetSimple(); void refetch(); },
        onError: (err) => alert(`保存失败：${err.message}`),
      },
    );
  }

  function submitWizard() {
    if (!wizardType || !wizardTpl) return;
    if (wizardType === "send_lawyer_letter" && !wizardFirmId) {
      alert("请选择合作律所");
      return;
    }
    createAction(
      {
        url: `legal/internal-orders/${id}/actions`,
        method: "post",
        values: {
          action_type: wizardType,
          note: wizardNote || undefined,
          letter_template_id: wizardTemplateId,
          partner_law_firm_id: wizardFirmId,
          letter_variables: wizardVars,
        },
      },
      {
        onSuccess: () => { alert("✓ 律师函记录已保存。请下载 PDF 找律师签字盖章后回来上传盖章版。"); resetWizard(); void refetch(); },
        onError: (err) => alert(`保存失败：${err.message}`),
      },
    );
  }

  function printLetter() {
    if (!wizardTpl) return;
    const body = renderTemplate(wizardTpl, wizardVars);
    const w = window.open("", "_blank", "width=800,height=900");
    if (!w) { alert("打印窗口被浏览器拦截，请允许弹窗后重试"); return; }
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${wizardTpl.name}</title>
      <style>
        @page { size: A4; margin: 25mm 20mm; }
        body { font-family: -apple-system, "Microsoft YaHei", sans-serif; font-size: 14px; line-height: 1.8; color: #111; }
        h1 { text-align: center; font-size: 22px; margin: 0 0 24px; letter-spacing: 4px; }
        .body { white-space: pre-wrap; word-break: break-word; }
        .footer { margin-top: 60px; text-align: right; color: #555; font-size: 12px; border-top: 1px solid #ddd; padding-top: 10px; }
      </style></head><body>
      <h1>${wizardTpl.name}</h1>
      <div class="body">${body.replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c] || c))}</div>
      <div class="footer">本文件由「有证慧催」系统生成 · 仅供内部草拟参考</div>
      <script>window.onload = () => { window.print(); };</script>
      </body></html>`);
    w.document.close();
  }

  function submitClose() {
    if (!closeReason) return;
    if (closeReason === "promised" && !promiseDate) {
      alert("请填写业主承诺缴清的日期");
      return;
    }
    if (!confirm(`确认关闭订单：${CLOSE_REASON_LABEL[closeReason]}?`)) return;
    closeOrder(
      {
        url: `legal/internal-orders/${id}/close`,
        method: "post",
        values: {
          close_reason: closeReason,
          note: closeNote || undefined,
          promise_due_date: closeReason === "promised" ? promiseDate : undefined,
        },
      },
      {
        onSuccess: () => { alert("✓ 订单已关闭"); resetClose(); void refetch(); },
        onError: (err) => alert(`关闭失败：${err.message}`),
      },
    );
  }

  function submitEscalate() {
    if (!confirm("确认升级到律所？升级后订单状态变为「已升级律所」，由 admin 撮合具体律所跟进。")) return;
    escalate(
      { url: `legal/internal-orders/${id}/escalate`, method: "post", values: {} },
      {
        onSuccess: () => { alert("✓ 已升级"); void refetch(); },
        onError: (err) => alert(`升级失败：${err.message}`),
      },
    );
  }

  function submitReopen() {
    if (!confirm(`承诺到期日 ${order?.promise_due_date} 已过，重新打开订单回处理中？`)) return;
    reopen(
      { url: `legal/internal-orders/${id}/reopen`, method: "post", values: { note: "承诺到期未付，重新打开" } },
      {
        onSuccess: () => { alert("✓ 订单已重新打开"); void refetch(); },
        onError: (err) => alert(`操作失败：${err.message}`),
      },
    );
  }

  function triggerUpload(actionId: number) {
    setUploadingActionId(actionId);
    fileInputRef.current?.click();
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";  // 允许同名文件再次选择
    if (!file || uploadingActionId == null) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = localStorage.getItem("token") ?? "";
      const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:18000/api/v1";
      const resp = await fetch(`${apiBase}/legal/internal-orders/${id}/actions/${uploadingActionId}/attachment`, {
        method: "POST",
        body: fd,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(`上传失败：${err.detail?.message ?? resp.statusText}`);
        return;
      }
      alert("✓ 附件已上传");
      void refetch();
    } finally {
      setUploadingActionId(null);
    }
  }

  function downloadAttachment(actionId: number) {
    const token = localStorage.getItem("token") ?? "";
    const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:18000/api/v1";
    fetch(`${apiBase}/legal/internal-orders/${id}/actions/${actionId}/attachment`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.blob() : Promise.reject(r.statusText))
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      })
      .catch((err) => alert(`下载失败：${err}`));
  }

  return (
    <div>
      <input ref={fileInputRef} type="file" accept="application/pdf,image/png,image/jpeg" style={{ display: "none" }} onChange={handleFileChange} />

      <div className="breadcrumb">
        <button type="button" onClick={() => navigate(-1)} className="ds-btn ds-btn-ghost ds-btn-sm" style={{ padding: 0 }}>
          <ArrowLeft className="w-3.5 h-3.5" /> 返回
        </button>
        <span className="sep">›</span>
        <span className="current">法务订单 #{order.id}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px minmax(0, 1fr) 280px", gap: 16, alignItems: "start" }}>
        {/* ── 左：业主信息 ── */}
        <div className="ds-card section-gap">
          <div className="card-header"><span className="card-title">业主信息</span></div>
          <div className="card-body">
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 16, fontWeight: 700 }}>{order.owner_name}</div>
              <div style={{ fontSize: 13, color: "#6b7280" }}>{room}</div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className="info-label">手机号</div>
              <div className="info-value" style={{ fontFamily: "var(--font-mono, monospace)" }}>
                {order.owner_phone_masked || "—"}
              </div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className="info-label">所属项目</div>
              <div className="info-value">{order.project_name || "—"}</div>
            </div>
            <div style={{ background: "#fef2f2", borderRadius: 8, padding: 14, textAlign: "center", marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>欠费金额</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#e02424" }}>¥{amount}</div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>共 {order.months_overdue ?? 0} 个月</div>
            </div>
            {order.arrears_reason && (
              <div style={{ padding: "10px 12px", background: "#fffbeb", borderRadius: 6, border: "1px solid #fde68a" }}>
                <div style={{ fontSize: 11, color: "#92400e", marginBottom: 2 }}>欠费理由</div>
                <div style={{ fontSize: 13, color: "#78350f" }}>{order.arrears_reason}</div>
              </div>
            )}
          </div>
        </div>

        {/* ── 中：actions 时间线 ── */}
        <div style={{ minWidth: 0 }}>
          <div className="ds-card">
            <div className="card-header"><span className="card-title">处理记录（{order.actions.length}）</span></div>
            <div className="card-body">
              {order.actions.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-title">暂无处理记录</div>
                  <div className="empty-desc">使用右侧操作栏开始内部处理流程</div>
                </div>
              ) : (
                <div className="timeline">
                  {order.actions.map((a: ActionOut) => {
                    const meta = ACTION_META[a.action_type] ?? ACTION_META.other;
                    const canAttach = a.action_type === "send_lawyer_letter" || a.action_type === "send_notice";
                    return (
                      <div key={a.id} className="tl-item">
                        <div className="tl-spine">
                          <div className={`tl-node ${meta.cls}`}>{meta.icon}</div>
                        </div>
                        <div className="tl-body">
                          <div className="tl-head">
                            <span className="tl-title">{meta.label}</span>
                            <span className="tl-meta">
                              {new Date(a.occurred_at).toLocaleString("zh-CN")}
                              {a.actor_name && ` · ${a.actor_name}`}
                            </span>
                          </div>
                          {a.letter_template_name && (
                            <div style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
                              📄 模板：{a.letter_template_name}
                              {a.partner_law_firm_name && ` · 律所：${a.partner_law_firm_name}`}
                            </div>
                          )}
                          {a.note && <div className="tl-text">{a.note}</div>}
                          {/* 附件区：已有附件显示链接，未有附件显示「上传盖章版」按钮（仅 send_lawyer_letter / send_notice）*/}
                          {canAttach && (
                            <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center" }}>
                              {a.attachment_filename ? (
                                <button
                                  type="button"
                                  onClick={() => downloadAttachment(a.id)}
                                  className="ds-btn ds-btn-ghost ds-btn-sm"
                                  style={{ color: "var(--color-primary)", padding: 0 }}
                                >
                                  <Paperclip className="w-3 h-3" /> {a.attachment_filename}
                                </button>
                              ) : !isClosed ? (
                                <button
                                  type="button"
                                  onClick={() => triggerUpload(a.id)}
                                  className="ds-btn ds-btn-ghost ds-btn-sm"
                                  style={{ color: "var(--color-neutral-500)", borderStyle: "dashed", border: "1px dashed var(--color-neutral-300)", padding: "4px 10px" }}
                                >
                                  <Upload className="w-3 h-3" /> 上传盖章版（PDF/JPG）
                                </button>
                              ) : null}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── 右：sticky 操作栏 ── */}
        <div style={{ position: "sticky", top: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          {/* v1.9.2 — 欠费分级处理建议（仅未关闭时显示）*/}
          {!isClosed && (() => {
            const sug = getProcessingSuggestion(order.amount_owed != null ? Number(order.amount_owed) : null);
            return sug ? (
              <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 6, padding: "10px 12px" }}>
                <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                  <Lightbulb size={14} style={{ color: sug.color, flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontSize: 11, color: "#92400e", marginBottom: 2, fontWeight: 600 }}>处理建议</div>
                    <div style={{ fontSize: 12, color: "#78350f", lineHeight: 1.55 }}>{sug.text}</div>
                  </div>
                </div>
              </div>
            ) : null;
          })()}

          {isClosed ? (
            <div className="ds-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>订单已关闭</div>
              <div style={{ fontSize: 13 }}>
                关闭原因：<strong>{CLOSE_REASON_LABEL[order.internal_close_reason || ""] || "—"}</strong>
              </div>
              <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginTop: 4 }}>
                {order.internal_closed_at && new Date(order.internal_closed_at).toLocaleString("zh-CN")}
              </div>
              {/* v1.9.1 — closed_promised 时显示承诺到期日；过期标红 + 重新打开按钮 */}
              {isClosedPromised && order.promise_due_date && (
                <>
                  <hr style={{ margin: "10px 0", border: "none", borderTop: "1px solid var(--color-neutral-200)" }} />
                  <div style={{ fontSize: 12, marginBottom: 6 }}>
                    业主承诺缴清日：<strong style={{ color: overdue ? "#dc2626" : "var(--color-neutral-900)" }}>{order.promise_due_date}</strong>
                    {overdue && <span className="ds-badge ds-badge-red" style={{ marginLeft: 6 }}>已过期</span>}
                  </div>
                  {overdue && (
                    <button
                      type="button" className="ds-btn ds-btn-secondary"
                      style={{ width: "100%", justifyContent: "center", color: "#dc2626", borderColor: "#fca5a5", marginTop: 6 }}
                      onClick={submitReopen}
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> 重新打开订单
                    </button>
                  )}
                </>
              )}
            </div>
          ) : (
            <>
              {/* 操作按钮组（默认）*/}
              {simpleType === null && wizardType === null && closeReason === null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>处理动作</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <ActionBtn icon={<MessageCircle className="w-3.5 h-3.5" />} label="记录沟通" onClick={() => setSimpleType("contact_owner")} />
                    <ActionBtn icon={<Mail className="w-3.5 h-3.5" />} label="起草律师函" onClick={() => { setWizardType("send_lawyer_letter"); setWizardStep(0); }} />
                    <ActionBtn icon={<Mail className="w-3.5 h-3.5" />} label="起草催告函" onClick={() => { setWizardType("send_notice"); setWizardStep(0); }} />
                    <ActionBtn icon={<Handshake className="w-3.5 h-3.5" />} label="记录调解" onClick={() => setSimpleType("mediation")} />
                    <ActionBtn icon={<FileText className="w-3.5 h-3.5" />} label="其他备注" onClick={() => setSimpleType("other")} />
                  </div>
                  <hr style={{ margin: "12px 0", border: "none", borderTop: "1px solid var(--color-neutral-200)" }} />
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>关闭订单</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <CloseBtn icon={<CheckCircle2 className="w-3.5 h-3.5" />} label="✓ 已缴清" reason="paid" color="#16a34a" onClick={setCloseReason} />
                    <CloseBtn icon={<Gavel className="w-3.5 h-3.5" />} label="📝 已承诺" reason="promised" color="#ea580c" onClick={setCloseReason} />
                    <CloseBtn icon={<AlertCircle className="w-3.5 h-3.5" />} label="❌ 无法催收" reason="uncollectible" color="#6b7280" onClick={setCloseReason} />
                    <button
                      type="button" className="ds-btn ds-btn-secondary"
                      style={{ width: "100%", justifyContent: "center", color: "#dc2626", borderColor: "#fca5a5", marginTop: 4 }}
                      onClick={submitEscalate}
                      title="内部处理无法解决，升级到律所走诉讼"
                    >
                      <ShieldAlert className="w-3.5 h-3.5" />
                      升级到律所
                    </button>
                  </div>
                </div>
              )}

              {/* 普通 action 表单（沟通 / 调解 / 备注）*/}
              {simpleType !== null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>
                    {ACTION_META[simpleType]?.label ?? "操作"}
                  </div>
                  <textarea
                    className="form-control"
                    placeholder="备注 / 沟通内容 / 调解结果..."
                    style={{ height: 100 }}
                    value={simpleNote}
                    onChange={(e) => setSimpleNote(e.target.value)}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button type="button" className="ds-btn ds-btn-secondary" style={{ flex: 1 }} onClick={resetSimple}>取消</button>
                    <button type="button" className="ds-btn ds-btn-primary" style={{ flex: 2 }} onClick={submitSimple}>保存记录</button>
                  </div>
                </div>
              )}

              {/* 关闭表单 */}
              {closeReason !== null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>
                    确认关闭：{CLOSE_REASON_LABEL[closeReason]}
                  </div>
                  {closeReason === "promised" && (
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>
                        业主承诺缴清日 *
                      </label>
                      <input
                        type="date"
                        className="form-control"
                        value={promiseDate}
                        min={todayISO()}
                        onChange={(e) => setPromiseDate(e.target.value)}
                      />
                      <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 4 }}>
                        到期未付时列表会标红 + 一键「重新打开」
                      </div>
                    </div>
                  )}
                  <textarea
                    className="form-control"
                    placeholder="关闭备注（可选）"
                    style={{ height: 80 }}
                    value={closeNote}
                    onChange={(e) => setCloseNote(e.target.value)}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button type="button" className="ds-btn ds-btn-secondary" style={{ flex: 1 }} onClick={resetClose}>取消</button>
                    <button type="button" className="ds-btn ds-btn-primary" style={{ flex: 2 }} onClick={submitClose}>确认关闭</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── 律师函起草 Wizard 弹窗 ── */}
      {wizardType !== null && (
        <div className="modal-overlay" onClick={resetWizard}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760, width: "92%" }}>
            <div className="modal-header">
              <span className="modal-title">
                {wizardType === "send_lawyer_letter" ? "起草律师函" : "起草催告函"}
                <span style={{ marginLeft: 12, fontSize: 12, color: "var(--color-neutral-500)" }}>
                  {["1. 选择模板", "2. 填写变量", "3. 预览 & 保存"][wizardStep]}
                </span>
              </span>
              <button type="button" className="modal-close" onClick={resetWizard}>×</button>
            </div>

            {/* Step 0: 选模板 + 律所 */}
            {wizardStep === 0 && (
              <div className="modal-body" style={{ padding: 20 }}>
                <div style={{ marginBottom: 14 }}>
                  <label className="form-label" style={{ display: "block", marginBottom: 6 }}>选择模板</label>
                  <select
                    className="form-control"
                    value={wizardTemplateId ?? ""}
                    onChange={(e) => {
                      const tid = e.target.value ? Number(e.target.value) : null;
                      setWizardTemplateId(tid);
                      const tpl = templates.find((t) => t.id === tid) ?? null;
                      autofillVars(tpl);
                    }}
                  >
                    <option value="">— 选择模板 —</option>
                    {templates
                      .filter((t) => wizardType === "send_lawyer_letter" ? t.category === "lawyer_letter" : t.category === "notice" || t.category === "reminder")
                      .map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>
                {wizardType === "send_lawyer_letter" && (
                  <div style={{ marginBottom: 14 }}>
                    <label className="form-label" style={{ display: "block", marginBottom: 6 }}>合作律所（盖章方）*</label>
                    <select
                      className="form-control"
                      value={wizardFirmId ?? ""}
                      onChange={(e) => setWizardFirmId(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">— 选择律所 —</option>
                      {firms.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  </div>
                )}
                <div className="modal-footer" style={{ marginTop: 12 }}>
                  <button type="button" className="ds-btn ds-btn-secondary" onClick={resetWizard}>取消</button>
                  <button
                    type="button" className="ds-btn ds-btn-primary"
                    disabled={!wizardTemplateId || (wizardType === "send_lawyer_letter" && !wizardFirmId)}
                    onClick={() => setWizardStep(1)}
                  >
                    下一步：填写变量
                  </button>
                </div>
              </div>
            )}

            {/* Step 1: 填变量（已知字段灰底自动填，未知字段需填）*/}
            {wizardStep === 1 && wizardTpl && (
              <div className="modal-body" style={{ padding: 20 }}>
                <div style={{ fontSize: 12, color: "var(--color-neutral-600)", marginBottom: 12 }}>
                  系统已自动填充已知字段（业主信息 / 楼栋 / 欠费金额 / 项目）；请补全律师签名等空白项。
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {(wizardTpl.variables ?? []).map((v) => {
                    const isKnown = KNOWN_VARS.has(v.name);
                    return (
                      <div key={v.name}>
                        <label className="form-label" style={{ display: "block", marginBottom: 4, fontSize: 12 }}>
                          {v.label} {!isKnown && <span style={{ color: "#dc2626" }}>*</span>}
                          {isKnown && <span style={{ marginLeft: 4, fontSize: 11, color: "var(--color-neutral-400)" }}>（自动）</span>}
                        </label>
                        <input
                          type={v.type === "date" ? "date" : "text"}
                          className="form-control"
                          value={wizardVars[v.name] ?? ""}
                          onChange={(e) => setWizardVars({ ...wizardVars, [v.name]: e.target.value })}
                          style={isKnown ? { background: "#f3f4f6", color: "#6b7280" } : {}}
                          readOnly={isKnown}
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="modal-footer" style={{ marginTop: 16 }}>
                  <button type="button" className="ds-btn ds-btn-secondary" onClick={() => setWizardStep(0)}>上一步</button>
                  <button type="button" className="ds-btn ds-btn-primary" onClick={() => setWizardStep(2)}>下一步：预览</button>
                </div>
              </div>
            )}

            {/* Step 2: 预览 & 保存 */}
            {wizardStep === 2 && wizardTpl && (
              <div className="modal-body" style={{ padding: 20 }}>
                <div style={{ background: "#fff", border: "1px solid var(--color-neutral-200)", borderRadius: 6, padding: 24, maxHeight: 400, overflow: "auto" }}>
                  <h2 style={{ textAlign: "center", marginBottom: 16, fontSize: 18, letterSpacing: 4 }}>{wizardTpl.name}</h2>
                  <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "inherit", fontSize: 13, lineHeight: 1.8, color: "#111", margin: 0 }}>
                    {renderTemplate(wizardTpl, wizardVars)}
                  </pre>
                </div>
                <div style={{ marginTop: 12 }}>
                  <label className="form-label" style={{ display: "block", marginBottom: 4, fontSize: 12 }}>备注（保存到处理记录）</label>
                  <textarea
                    className="form-control"
                    style={{ height: 60 }}
                    placeholder="如：首次发函，要求 7 日内回款"
                    value={wizardNote}
                    onChange={(e) => setWizardNote(e.target.value)}
                  />
                </div>
                <div className="modal-footer" style={{ marginTop: 16, display: "flex", gap: 8 }}>
                  <button type="button" className="ds-btn ds-btn-secondary" onClick={() => setWizardStep(1)}>上一步</button>
                  <div style={{ flex: 1 }} />
                  <button type="button" className="ds-btn ds-btn-secondary" onClick={printLetter}>
                    <Printer className="w-3.5 h-3.5" /> 打印 / 下载 PDF
                  </button>
                  <button type="button" className="ds-btn ds-btn-primary" onClick={submitWizard}>
                    保存记录
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ActionBtn({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button type="button" className="ds-btn ds-btn-secondary" style={{ width: "100%", justifyContent: "center" }} onClick={onClick}>
      {icon} {label}
    </button>
  );
}

function CloseBtn({ icon, label, reason, color, onClick }: { icon: React.ReactNode; label: string; reason: string; color: string; onClick: (r: string) => void }) {
  return (
    <button
      type="button" className="ds-btn ds-btn-ghost"
      style={{ width: "100%", justifyContent: "center", color, borderColor: color, fontSize: 12 }}
      onClick={() => onClick(reason)}
    >
      {icon} {label}
    </button>
  );
}
