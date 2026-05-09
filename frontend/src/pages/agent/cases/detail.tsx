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
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
import { QrDialDialog } from "../../../components/dial/QrDialDialog";
import type { CaseDetailResponse } from "../../../types/case";

export function AgentWorkstationPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [qrState, setQrState] = useState<{ caseId: number; qrPayload: string; expiresAt: string } | null>(null);
  const [showDiscountModal, setShowDiscountModal] = useState(false);

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
    if (!detail) return;
    const description = window.prompt("工单内容（必填）：");
    if (!description?.trim()) return;
    customMutate(
      {
        url: "workorders",
        method: "post",
        values: {
          case_id: detail.id,
          order_type: "case_followup",
          description: description.trim(),
          priority: "normal",
        },
      },
      {
        onSuccess: (resp) => alert(`✓ 工单 #${(resp.data as { id?: number }).id ?? "?"} 已创建`),
        onError: (err) => alert(`建工单失败：${err.message}`),
      },
    );
  }

  function handleIntent(action: "transfer_supervisor" | "transfer_legal", label: string) {
    if (!detail) return;
    customMutate(
      { url: `agent/cases/${detail.id}/intent`, method: "post", values: { action } },
      {
        onSuccess: () => alert(`✓ ${label} 已记录，等待业务流程接入`),
        onError: (err) => alert(`${label} 失败：${err.message}`),
      },
    );
  }

  function handleSendPaymentLink() {
    if (!detail) return;
    customMutate(
      { url: `agent/cases/${detail.id}/send-payment-link`, method: "post", values: {} },
      {
        onSuccess: (resp) => {
          const data = resp.data as { short_link?: string; sent_to?: string };
          alert(`✓ 已发送缴费链接到 ${data.sent_to ?? "业主"}\n短链：${data.short_link ?? "—"}`);
        },
        onError: (err) => alert(`发送失败：${err.message}`),
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

        {/* ── 中：活动时间线 + 添加跟进备注 ── */}
        <div style={{ minWidth: 0 }}>
          <ActivityTimeline
            calls={detail.calls}
            timelineEvents={detail.timeline_events}
            createdAt={detail.created_at}
          />

          <FollowUpNoteCard
            caseId={detail.id}
            endpoint={`agent/cases/${detail.id}/stage`}
            invalidateResource="agent/cases"
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
                title="发起减免 / 分期 / 违约金减免申请，督导或 admin 审批"
              >
                <BadgePercent className="w-3.5 h-3.5" />
                申请减免
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => handleIntent("transfer_supervisor", "升级督导")}
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
                onClick={() => handleIntent("transfer_legal", "申请转法务")}
                title="提交转法务申请，督导/admin 审批后真正转化"
              >
                <Scale className="w-3.5 h-3.5" />
                申请转法务
              </button>
            </div>
          </div>

          <div style={{ fontSize: 11, color: "var(--color-neutral-400)", textAlign: "center", lineHeight: 1.6 }}>
            「申请转法务」会提交申请单<br/>督导/admin 审批后才会真正转化
          </div>
        </div>
      </div>

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
    </div>
  );
}
