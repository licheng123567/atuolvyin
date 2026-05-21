// 督导侧案件详情 — v1.6.9
// 重写：复用 admin/agent 同款 build_case_detail_response 后端 + 共享组件
// 三栏布局（与 agent 详情页一致）：左 业主+项目+欠费 / 中 时间线+备注 / 右 sticky 操作
import { useCustomMutation, useGetIdentity, useInvalidate, useOne } from "@refinedev/core";
import {
  ArrowLeft,
  BadgePercent,
  ClipboardList,
  CreditCard,
  Eye,
  Phone,
  Scale,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { FollowUpNoteCard } from "../../../components/case/FollowUpNoteCard";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import { DiscountRequestModal } from "../../../components/discount/DiscountRequestModal";
import {
  PaymentLinkQrModal,
  type PaymentBreakdown,
} from "../../../components/admin/PaymentLinkQrModal";
import { WorkOrderCreateModal } from "../../../components/admin/WorkOrderCreateModal";
import {
  SupervisorCaseActionModal,
  type SupervisorActionType,
} from "../../../components/supervisor/SupervisorCaseActionModal";
import { SupervisorReassignModal } from "../../../components/supervisor/SupervisorReassignModal";
// v0.6.0 — 法务转化按钮条件渲染:无申请→「移交法务」(督导直接转);有申请→「审批转法务」(本页内 modal)
import { LegalConversionApprovalModal } from "../../../components/supervisor/LegalConversionApprovalModal";
import { TransferLegalDirectModal } from "../../../components/supervisor/TransferLegalDirectModal";
import type { AuthUser } from "../../../providers/auth-provider";
import type { CaseDetailResponse } from "../../../types/case";

export function SupervisorCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: identity } = useGetIdentity<AuthUser>();
  const [showDiscountModal, setShowDiscountModal] = useState(false);
  // v0.5.4 — 督导动作弹窗 state
  const [actionType, setActionType] = useState<SupervisorActionType | null>(null);
  const [reassignOpen, setReassignOpen] = useState(false);
  // v0.6.0 — 法务转化按钮(分两路:transfer-legal-direct / approve-existing-request)
  const [transferLegalOpen, setTransferLegalOpen] = useState(false);
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  // v0.5.4 — Wave 6:督导也可发缴费链接 / 创建工单(后端守卫已含 supervisor)
  const [workOrderOpen, setWorkOrderOpen] = useState(false);
  const [paymentLink, setPaymentLink] = useState<{
    token: string;
    breakdown: PaymentBreakdown;
    sent_to: string;
  } | null>(null);
  const { mutate: sendPaymentLink, mutation: paymentLinkMutation } =
    useCustomMutation();
  const invalidate = useInvalidate();

  function refresh() {
    void invalidate({ resource: "supervisor/cases", invalidates: ["all"] });
  }

  function handleSendPaymentLink(caseId: number) {
    sendPaymentLink(
      {
        url: `admin/cases/${caseId}/send-payment-link`,
        method: "post",
        values: {},
      },
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
        onError: () => alert("生成缴费链接失败,请重试"),
      },
    );
  }

  const { query } = useOne<CaseDetailResponse>({
    resource: "supervisor/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id, retry: false },
  });
  const detail = query.data?.data;

  // 仅 supervisor + admin 可发起减免；legal 角色只读
  const canAct =
    identity?.role === "supervisor" ||
    identity?.role === "admin" ||
    identity?.role === "superadmin";

  if (query.isLoading) {
    return (
      <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>
        加载中…
      </div>
    );
  }
  if (!detail) {
    return (
      <div style={{ padding: 32, color: "var(--color-danger)" }}>
        案件不存在或无权访问
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          返回
        </button>
        <span className="sep">›</span>
        <span className="current">CC-{String(detail.id).padStart(4, "0")}</span>
      </div>

      {/* 三栏：320 业主+项目+欠费 / 1fr 时间线 / 260 sticky 操作 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "320px minmax(0, 1fr) 260px",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* ── 左：业主信息 + 项目情况 + 欠费明细 ── */}
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
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div className="ds-card" style={{ padding: 14 }}>
            <div
              style={{
                fontSize: 12.5,
                fontWeight: 700,
                color: "#374151",
                marginBottom: 10,
              }}
            >
              督导操作
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {canAct && (
                <button
                  type="button"
                  className="ds-btn ds-btn-primary"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    color: "white",
                    background: "#b45309",
                    borderColor: "#b45309",
                  }}
                  onClick={() => setShowDiscountModal(true)}
                  title="发起减免/分期/违约金减免，按金额自动判定走督导/物业管理员审批"
                >
                  <BadgePercent className="w-3.5 h-3.5" />
                  发起减免
                </button>
              )}
              {/* v0.6.0 — 「介入处理」按钮去掉:升级案件页已统一处理(5 选项弹窗内嵌)。
                  这里继续保留时入口重复,用户反馈混乱 — 让该入口只走「升级案件处理」页。 */}
              {/* v0.6.0 — 条件渲染:无申请 → 督导直接「移交法务」;有申请 → 「审批转法务」 */}
              {detail.pending_legal_conversion_request_id ? (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    color: "white",
                    background: "#7e3af2",
                    borderColor: "#7e3af2",
                  }}
                  onClick={() => setApprovalModalOpen(true)}
                  title="案件下有催收员提交的法务转化申请,点击审批"
                >
                  <Scale className="w-3.5 h-3.5" />
                  审批转法务
                </button>
              ) : (
                detail.stage !== "legal" && (
                  <button
                    type="button"
                    className="ds-btn ds-btn-secondary"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={() => setTransferLegalOpen(true)}
                    title="督导直接移交法务(跳过催收员申请-审批流;需填原因审计)"
                  >
                    <Scale className="w-3.5 h-3.5" />
                    移交法务
                  </button>
                )
              )}
              {detail.assigned_to && (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => setReassignOpen(true)}
                  title="重新分配给其他催收员"
                >
                  <Users className="w-3.5 h-3.5" />
                  重新分配
                </button>
              )}
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => setActionType("urge")}
                title="对停滞案件发催办,推送通知给催收员"
              >
                <Phone className="w-3.5 h-3.5" />
                催办
              </button>
              {/* v0.6.0 — 「催回访」与上方「催办」语义重合,用户反馈合并,只保留「催办」。
                  原 SupervisorCaseActionModal type="remind_callback" 后端独立 endpoint
                  暂时保留(其他入口可能仍用),前端入口在此移除。 */}
              {/* v0.5.4 Wave 6 — 督导也可发缴费链接(后端守卫含 supervisor)*/}
              <button
                type="button"
                onClick={() => handleSendPaymentLink(detail.id)}
                disabled={paymentLinkMutation.isPending}
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                title="生成业主缴费链接(明细 + 二维码弹窗)"
              >
                <CreditCard className="w-3.5 h-3.5" />
                {paymentLinkMutation.isPending ? "生成中…" : "发送缴费链接"}
              </button>
              {/* v0.5.4 Wave 6 — 督导也可建工单 */}
              <button
                type="button"
                onClick={() => setWorkOrderOpen(true)}
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                title="对此案件相关问题创建工单,自动派单给协调员"
              >
                <ClipboardList className="w-3.5 h-3.5" />
                创建工单
              </button>
              {/* v0.5.4 — 通话历史按钮删除:案件通话已在中栏 ActivityTimeline 里以「📞 通话」事件呈现,不再需要单独入口 */}
            </div>
          </div>

          <div
            className="ds-card"
            style={{ padding: 12, fontSize: 11, color: "var(--color-neutral-500)", lineHeight: 1.7 }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
              <Eye size={11} /> 当前归属
            </div>
            <div style={{ color: "var(--color-neutral-700)" }}>
              {detail.assigned_to
                ? `催收员 #${detail.assigned_to}（${detail.assigned_role ?? "—"}）`
                : "未分配（公海）"}
            </div>
            <div style={{ marginTop: 6 }}>
              池类型：<strong>{detail.pool_type === "public" ? "公海" : "私海"}</strong>
            </div>
            <div>
              当前阶段：<strong>{detail.stage}</strong>
            </div>
          </div>

          {/* v1.6.11 — 跟进备注移到右栏（操作完直接写） */}
          {canAct && (
            <FollowUpNoteCard
              caseId={detail.id}
              endpoint={`admin/cases/${detail.id}/stage`}
              invalidateResource="supervisor/cases"
            />
          )}
        </div>
      </div>

      {showDiscountModal && (
        <DiscountRequestModal
          caseId={detail.id}
          originalAmount={detail.amount_owed != null ? Number(detail.amount_owed) : null}
          ownerName={detail.owner.name}
          onClose={() => setShowDiscountModal(false)}
          onSuccess={(offerId) => {
            setShowDiscountModal(false);
            alert(`✓ 减免申请 #${offerId} 已提交`);
            navigate("/supervisor/discount-approvals");
          }}
        />
      )}

      {actionType && (
        <SupervisorCaseActionModal
          caseId={detail.id}
          type={actionType}
          onClose={() => setActionType(null)}
          onDone={() => {
            setActionType(null);
            refresh();
            alert("✓ 已写入案件时间线并通知催收员");
          }}
        />
      )}

      {reassignOpen && (
        <SupervisorReassignModal
          caseId={detail.id}
          currentAssignedTo={detail.assigned_to ?? null}
          onClose={() => setReassignOpen(false)}
          onDone={() => {
            setReassignOpen(false);
            refresh();
            alert("✓ 案件已重新分配,新催收员收到通知");
          }}
        />
      )}

      {workOrderOpen && (
        <WorkOrderCreateModal
          caseId={detail.id}
          onClose={() => setWorkOrderOpen(false)}
          onSuccess={(orderId) => {
            setWorkOrderOpen(false);
            alert(`工单 #${orderId ?? "?"} 已创建,已自动派单给协调员`);
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

      {/* v0.6.0 — 督导直接移交法务弹窗(无申请时) */}
      {transferLegalOpen && (
        <TransferLegalDirectModal
          caseId={detail.id}
          caseLabel={`${detail.owner.name} · #${detail.id}`}
          onClose={() => setTransferLegalOpen(false)}
          onDone={() => {
            setTransferLegalOpen(false);
            refresh();
            alert("✓ 案件已直接移交法务");
          }}
        />
      )}

      {/* v0.6.0 — 审批催收员转法务申请(有申请时) */}
      {approvalModalOpen && detail.pending_legal_conversion_request_id && (
        <LegalConversionApprovalModal
          requestId={detail.pending_legal_conversion_request_id}
          caseLabel={`${detail.owner.name} · #${detail.id}`}
          onClose={() => setApprovalModalOpen(false)}
          onDone={() => {
            setApprovalModalOpen(false);
            refresh();
            alert("✓ 审批已提交");
          }}
        />
      )}
    </div>
  );
}
