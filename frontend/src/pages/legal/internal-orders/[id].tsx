// v1.9.0 — 法务订单内部处理详情页
// 三栏：左 业主信息 / 中 actions 时间线 / 右 sticky 操作按钮组
import { useCustom, useCustomMutation } from "@refinedev/core";
import { ArrowLeft, CheckCircle2, FileText, Gavel, Handshake, Mail, MessageCircle, ShieldAlert } from "lucide-react";
import { useState } from "react";
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

  const { mutate: createAction } = useCustomMutation();
  const { mutate: closeOrder } = useCustomMutation();
  const { mutate: escalate } = useCustomMutation();

  const [actionType, setActionType] = useState<string | null>(null);
  const [actionNote, setActionNote] = useState("");
  const [letterTemplateId, setLetterTemplateId] = useState<number | null>(null);
  const [partnerFirmId, setPartnerFirmId] = useState<number | null>(null);
  const [closeReason, setCloseReason] = useState<string | null>(null);
  const [closeNote, setCloseNote] = useState("");

  // 模板/律所候选
  const { query: templatesQuery } = useCustom<{ items: { id: number; name: string; category: string }[] }>({
    url: "admin/internal-letter-templates",
    method: "get",
    config: { query: { only_active: true, page_size: 100 } },
    queryOptions: { enabled: actionType === "send_lawyer_letter" || actionType === "send_notice" },
  });
  const { query: firmsQuery } = useCustom<{ items: { id: number; name: string }[] }>({
    url: "admin/partner-law-firms",
    method: "get",
    config: { query: { only_active: true, page_size: 100 } },
    queryOptions: { enabled: actionType === "send_lawyer_letter" },
  });
  const templates = templatesQuery.data?.data?.items ?? [];
  const firms = firmsQuery.data?.data?.items ?? [];

  if (isLoading) return <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>加载中…</div>;
  if (!order) return <div style={{ padding: 32, color: "var(--color-danger)" }}>订单不存在</div>;

  const room = (order.building || "") + (order.room || "") || "—";
  const amount = order.amount_owed != null ? Number(order.amount_owed).toLocaleString("zh-CN") : "—";

  function resetActionForm() {
    setActionType(null);
    setActionNote("");
    setLetterTemplateId(null);
    setPartnerFirmId(null);
  }

  function submitAction() {
    if (!actionType) return;
    createAction(
      {
        url: `legal/internal-orders/${id}/actions`,
        method: "post",
        values: {
          action_type: actionType,
          note: actionNote || undefined,
          letter_template_id: letterTemplateId,
          partner_law_firm_id: partnerFirmId,
        },
      },
      {
        onSuccess: () => {
          alert("✓ 已记录");
          resetActionForm();
          void refetch();
        },
        onError: (err) => alert(`保存失败：${err.message}`),
      },
    );
  }

  function submitClose() {
    if (!closeReason) return;
    if (!confirm(`确认关闭订单：${CLOSE_REASON_LABEL[closeReason]}?`)) return;
    closeOrder(
      {
        url: `legal/internal-orders/${id}/close`,
        method: "post",
        values: { close_reason: closeReason, note: closeNote || undefined },
      },
      {
        onSuccess: () => {
          alert("✓ 订单已关闭");
          setCloseReason(null);
          setCloseNote("");
          void refetch();
        },
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

  return (
    <div>
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
                          {a.attachment_filename && (
                            <div style={{ fontSize: 12, color: "var(--color-primary)", marginTop: 4 }}>
                              📎 {a.attachment_filename}
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
          {isClosed ? (
            <div className="ds-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>订单已关闭</div>
              <div style={{ fontSize: 13 }}>
                关闭原因：<strong>{CLOSE_REASON_LABEL[order.internal_close_reason || ""] || "—"}</strong>
              </div>
              <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginTop: 4 }}>
                {order.internal_closed_at && new Date(order.internal_closed_at).toLocaleString("zh-CN")}
              </div>
            </div>
          ) : (
            <>
              {/* 操作按钮组 */}
              {actionType === null && closeReason === null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>处理动作</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <ActionBtn icon={<MessageCircle className="w-3.5 h-3.5" />} label="记录沟通" onClick={() => setActionType("contact_owner")} />
                    <ActionBtn icon={<Mail className="w-3.5 h-3.5" />} label="出具律师函" onClick={() => setActionType("send_lawyer_letter")} />
                    <ActionBtn icon={<Mail className="w-3.5 h-3.5" />} label="出具催告函" onClick={() => setActionType("send_notice")} />
                    <ActionBtn icon={<Handshake className="w-3.5 h-3.5" />} label="记录调解" onClick={() => setActionType("mediation")} />
                    <ActionBtn icon={<FileText className="w-3.5 h-3.5" />} label="其他备注" onClick={() => setActionType("other")} />
                  </div>
                  <hr style={{ margin: "12px 0", border: "none", borderTop: "1px solid var(--color-neutral-200)" }} />
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>关闭订单</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <CloseBtn icon={<CheckCircle2 className="w-3.5 h-3.5" />} label="✓ 已缴清" reason="paid" color="#16a34a" onClick={setCloseReason} />
                    <CloseBtn icon={<Gavel className="w-3.5 h-3.5" />} label="📝 已承诺" reason="promised" color="#ea580c" onClick={setCloseReason} />
                    <CloseBtn icon={<Gavel className="w-3.5 h-3.5" />} label="❌ 无法催收" reason="uncollectible" color="#6b7280" onClick={setCloseReason} />
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

              {/* Action 表单 */}
              {actionType !== null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>
                    {ACTION_META[actionType]?.label ?? "操作"}
                  </div>
                  {(actionType === "send_lawyer_letter" || actionType === "send_notice") && (
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>选择模板</label>
                      <select
                        className="form-control"
                        value={letterTemplateId ?? ""}
                        onChange={(e) => setLetterTemplateId(e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">— 不使用模板 —</option>
                        {templates.map((t) => (
                          <option key={t.id} value={t.id}>{t.name}（{t.category}）</option>
                        ))}
                      </select>
                    </div>
                  )}
                  {actionType === "send_lawyer_letter" && (
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>合作律所（盖章方）</label>
                      <select
                        className="form-control"
                        value={partnerFirmId ?? ""}
                        onChange={(e) => setPartnerFirmId(e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">— 选择律所 —</option>
                        {firms.map((f) => (
                          <option key={f.id} value={f.id}>{f.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <textarea
                    className="form-control"
                    placeholder="备注 / 沟通内容 / 调解结果..."
                    style={{ height: 100 }}
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button type="button" className="ds-btn ds-btn-secondary" style={{ flex: 1 }} onClick={resetActionForm}>取消</button>
                    <button type="button" className="ds-btn ds-btn-primary" style={{ flex: 2 }} onClick={submitAction}>
                      保存记录
                    </button>
                  </div>
                </div>
              )}

              {/* 关闭表单 */}
              {closeReason !== null && (
                <div className="ds-card" style={{ padding: 14 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 10 }}>
                    确认关闭：{CLOSE_REASON_LABEL[closeReason]}
                  </div>
                  <textarea
                    className="form-control"
                    placeholder="关闭备注（可选）"
                    style={{ height: 80 }}
                    value={closeNote}
                    onChange={(e) => setCloseNote(e.target.value)}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button type="button" className="ds-btn ds-btn-secondary" style={{ flex: 1 }} onClick={() => { setCloseReason(null); setCloseNote(""); }}>取消</button>
                    <button type="button" className="ds-btn ds-btn-primary" style={{ flex: 2 }} onClick={submitClose}>确认关闭</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
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
