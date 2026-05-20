// frontend/src/pages/agent/cases/detail.tsx
// v1.6.6 — 催收员案件详情：双栏布局
// v1.6.8 — 三栏布局：左 业主信息+项目情况 / 中 时间线+跟进备注 / 右 sticky 操作按钮组
//          操作按钮始终右侧可见，无需滚动
import { useCustomMutation, useGo, useOne } from "@refinedev/core";
import { ArrowLeft, BadgePercent, ClipboardList, CreditCard, Headphones, Phone, Scale } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { FollowUpNoteCard } from "../../../components/case/FollowUpNoteCard";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import { EscalateSupervisorModal } from "../../../components/agent/EscalateSupervisorModal";
import {
  PaymentLinkQrModal,
  type PaymentBreakdown,
} from "../../../components/admin/PaymentLinkQrModal";
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
import { QrDialDialog } from "../../../components/dial/QrDialDialog";
import { RequestLegalConversionModal } from "../../../components/legal-conversion/RequestLegalConversionModal";
import type { CaseDetailResponse } from "../../../types/case";

export function AgentWorkstationPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [qrState, setQrState] = useState<{ caseId: number; qrPayload: string; expiresAt: string } | null>(null);
  const [showDiscountModal, setShowDiscountModal] = useState(false);
  // v0.5.4 — 申请转法务弹窗 state(替代 window.prompt 流)
  const [transferLegalOpen, setTransferLegalOpen] = useState(false);
  // v0.5.4 Wave 7 — 升级督导弹窗 state(加「什么情况下升级督导」指引)
  const [escalateOpen, setEscalateOpen] = useState(false);
  // v0.5.4 Wave 7 — 发缴费链接 → PaymentLinkQrModal(明细 + 二维码),与物业 admin 同款
  const [paymentLink, setPaymentLink] = useState<{
    token: string;
    breakdown: PaymentBreakdown;
    sent_to: string;
  } | null>(null);
  // v1.9.7 — 建工单 Modal（替换 window.prompt）
  const [woModalOpen, setWoModalOpen] = useState(false);
  const [woType, setWoType] = useState<"quality" | "reduction" | "dispute" | "other">("quality");
  const [woPriority, setWoPriority] = useState<"urgent_critical" | "urgent" | "normal" | "low">("normal");
  const [woReason, setWoReason] = useState("");

  const { query } = useOne<CaseDetailResponse>({
    resource: "agent/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });
  const detail = query.data?.data;
  const isLoading = query.isLoading;

  const { mutate: customMutate } = useCustomMutation();
  const { mutate: dialMutate } = useCustomMutation();

  function handleDial() {
    if (!detail) return;
    dialMutate(
      { url: "calls/dial-request", method: "post", values: { case_id: detail.id, mode: "qr" } },
      {
        onSuccess: (resp) => {
          const data = resp.data as { qr_payload?: string; expires_at?: string };
          if (data.qr_payload && data.expires_at) {
            setQrState({ caseId: detail.id, qrPayload: data.qr_payload, expiresAt: data.expires_at });
          } else {
            alert("拨号请求成功但未返回二维码");
          }
        },
        onError: (err) => alert(`拨号失败：${err.message ?? "未知错误"}`),
      },
    );
  }

  function handleCreateWorkOrder() {
    setWoModalOpen(true);
  }

  function submitNewWorkOrder() {
    if (!detail) return;
    if (!woReason.trim()) { alert("请填写工单原因"); return; }
    customMutate(
      {
        url: "workorders",
        method: "post",
        values: {
          case_id: detail.id,
          order_type: woType,
          description: woReason.trim(),
          priority: woPriority,
        },
      },
      {
        onSuccess: (resp) => {
          alert(`✓ 工单 #${(resp.data as { id?: number }).id ?? "?"} 已创建`);
          setWoModalOpen(false);
          setWoType("quality");
          setWoPriority("normal");
          setWoReason("");
        },
        onError: (err) => alert(`建工单失败：${err.message}`),
      },
    );
  }

  function handleSendPaymentLink() {
    if (!detail) return;
    customMutate(
      { url: `agent/cases/${detail.id}/send-payment-link`, method: "post", values: {} },
      {
        onSuccess: (resp) => {
          const d = resp.data as {
            token: string;
            sent_to: string;
            breakdown: PaymentBreakdown;
          };
          setPaymentLink({
            token: d.token,
            breakdown: d.breakdown,
            sent_to: d.sent_to,
          });
        },
        onError: (err) => alert(`发送失败:${err.message}`),
      },
    );
  }

  if (isLoading) {
    return <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>加载中…</div>;
  }
  if (!detail) {
    return <div style={{ padding: 32, color: "var(--color-danger)" }}>案件不存在或无权访问</div>;
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <button
          type="button"
          onClick={() => go({ to: "/agent/cases" })}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          我的案件
        </button>
        <span className="sep">›</span>
        <span className="current">CC-{String(detail.id).padStart(4, "0")}</span>
      </div>

      {/* v1.6.8 三栏布局：250 业主信息 / 1fr 时间线+跟进 / 260 sticky 操作 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "320px minmax(0, 1fr) 260px",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* ── 左：业主信息 + 项目情况 ── */}
        <div>
          <OwnerInfoCard detail={detail} />
          <ProjectInfoCard detail={detail} />
        </div>

        {/* ── 中：活动时间线 ── */}
        <div style={{ minWidth: 0 }}>
          <ActivityTimeline
            calls={detail.calls}
            timelineEvents={detail.timeline_events}
            createdAt={detail.created_at}
          />
        </div>

        {/* ── 右：sticky 操作按钮组 ── */}
        <div
          style={{
            position: "sticky",
            top: 16,
            display: "flex", flexDirection: "column", gap: 8,
          }}
        >
          <div
            className="ds-card"
            style={{ padding: 14 }}
          >
            <div style={{ fontSize: 12.5, fontWeight: 700, color: "#374151", marginBottom: 10 }}>
              快速操作
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
                disabled={detail.owner.do_not_call}
                onClick={handleDial}
                title={detail.owner.do_not_call ? "业主已加入免打扰" : "扫码到 App 拨号"}
              >
                <Phone className="w-3.5 h-3.5" />
                {detail.owner.do_not_call ? "业主免打扰" : "扫码 App 拨号"}
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={handleSendPaymentLink}
              >
                <CreditCard className="w-3.5 h-3.5" />
                发送缴费链接
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={handleCreateWorkOrder}
              >
                <ClipboardList className="w-3.5 h-3.5" />
                创建工单
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{
                  width: "100%", justifyContent: "center",
                  color: "#b45309", borderColor: "#fcd34d",
                }}
                onClick={() => setShowDiscountModal(true)}
                title="发起减免 / 分期 / 违约金减免申请，督导或物业管理员审批"
              >
                <BadgePercent className="w-3.5 h-3.5" />
                申请减免
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => setEscalateOpen(true)}
              >
                <Headphones className="w-3.5 h-3.5" />
                升级督导
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{
                  width: "100%", justifyContent: "center",
                  color: "#7e3af2", borderColor: "#c4b5fd",
                }}
                onClick={() => setTransferLegalOpen(true)}
                title="提交转法务申请,督导/物业管理员审批后由法务接单选服务包建单"
              >
                <Scale className="w-3.5 h-3.5" />
                申请转法务
              </button>
            </div>
          </div>

          <div style={{ fontSize: 11, color: "var(--color-neutral-400)", textAlign: "center", lineHeight: 1.6 }}>
            「申请转法务」会提交申请单<br/>督导/物业管理员审批后才会真正转化
          </div>

          {/* v1.6.11 — 跟进备注移到右栏（操作完直接写） */}
          <FollowUpNoteCard
            caseId={detail.id}
            endpoint={`agent/cases/${detail.id}/stage`}
            invalidateResource="agent/cases"
          />
        </div>
      </div>

      {transferLegalOpen && detail && (
        <RequestLegalConversionModal
          caseId={detail.id}
          onClose={() => setTransferLegalOpen(false)}
          onSubmitted={() => {
            setTransferLegalOpen(false);
            alert("✓ 申请转法务已提交,等待督导/物业管理员审批");
          }}
        />
      )}

      {escalateOpen && detail && (
        <EscalateSupervisorModal
          caseId={detail.id}
          onClose={() => setEscalateOpen(false)}
          onSubmitted={() => {
            setEscalateOpen(false);
            alert("✓ 已升级到督导队列");
          }}
        />
      )}

      {paymentLink && (
        <PaymentLinkQrModal
          token={paymentLink.token}
          breakdown={paymentLink.breakdown}
          sentTo={paymentLink.sent_to}
          onClose={() => setPaymentLink(null)}
        />
      )}

      {qrState && (
        <QrDialDialog
          qrPayload={qrState.qrPayload}
          expiresAt={qrState.expiresAt}
          onClose={() => setQrState(null)}
          onRegenerate={handleDial}
        />
      )}

      {showDiscountModal && (
        <DiscountRequestModal
          caseId={detail.id}
          originalAmount={detail.amount_owed != null ? Number(detail.amount_owed) : null}
          ownerName={detail.owner.name}
          onClose={() => setShowDiscountModal(false)}
          onSuccess={(offerId) => {
            setShowDiscountModal(false);
            alert(`✓ 减免申请 #${offerId} 已提交，等待审批`);
          }}
        />
      )}

      {/* v1.9.7 — 建工单 Modal（替换 window.prompt） */}
      {woModalOpen && (
        <div className="modal-overlay" onClick={() => setWoModalOpen(false)}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div className="modal-header">
              <span className="modal-title">新建工单 · {detail.owner.name}</span>
              <button type="button" className="modal-close" onClick={() => setWoModalOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">工单类型 <span className="req">*</span></label>
                  <select
                    className="form-control"
                    value={woType}
                    onChange={(e) => setWoType(e.target.value as "quality" | "reduction" | "dispute" | "other")}
                  >
                    <option value="quality">服务质量</option>
                    <option value="reduction">减免申请</option>
                    <option value="dispute">业主纠纷</option>
                    <option value="other">其他</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">优先级</label>
                  <select
                    className="form-control"
                    value={woPriority}
                    onChange={(e) => setWoPriority(e.target.value as "urgent_critical" | "urgent" | "normal" | "low")}
                  >
                    <option value="urgent_critical">紧急-严重</option>
                    <option value="urgent">紧急</option>
                    <option value="normal">普通</option>
                    <option value="low">低</option>
                  </select>
                </div>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">工单原因 <span className="req">*</span></label>
                <textarea
                  className="form-control"
                  style={{ height: 110 }}
                  placeholder="例：业主反映 5 楼电梯已停运 3 天，多次催修未果，已联系维保但无人响应…"
                  value={woReason}
                  onChange={(e) => setWoReason(e.target.value)}
                />
                <div style={{ fontSize: 11, color: "var(--color-neutral-500)", marginTop: 4 }}>
                  提交后此内容将作为工单原因记录，<strong>创建后不可修改</strong>（用于审计基线）；协调员处理过程在「跟进记录」补充。
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="ds-btn ds-btn-secondary" onClick={() => setWoModalOpen(false)}>取消</button>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                onClick={submitNewWorkOrder}
                disabled={!woReason.trim()}
              >提交工单</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
