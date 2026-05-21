// 1:1 还原 ui/admin.html#a-case-detail 案件详情
// v1.6.6 — 业主信息 / 项目基本情况 / 活动时间线 抽到 components/case/* 共享给 agent
import { useGetIdentity, useGo, useInvalidate, useOne, useCustomMutation } from "@refinedev/core";
import type { AuthUser } from "../../../providers/auth-provider";
import { ArrowLeft, ClipboardList, CreditCard, Download, Scale, Users } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { CaseDetailResponse } from "../../../types/case";
import { ConvertToLegalModal } from "../../../components/legal-conversion/ConvertToLegalModal";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { FollowUpNoteCard } from "../../../components/case/FollowUpNoteCard";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
// v0.6.0 — 分配/重新分配改用右侧 Drawer(原中间弹窗下拉太挤)
import { AdminAssignDrawer } from "../../../components/admin/AdminAssignDrawer";
import { WorkOrderCreateModal } from "../../../components/admin/WorkOrderCreateModal";
import { PaymentLinkQrModal } from "../../../components/admin/PaymentLinkQrModal";
import type { PaymentBreakdown } from "../../../components/admin/PaymentLinkQrModal";
// v0.8.0 Wave C — 案件证据状态小卡片(右栏顶)
import { EvidenceStatusBadge } from "../../../components/evidence/EvidenceStatusBadge";

export function AdminCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();

  // v1.4 — PM 角色只读：admin/cases 路由放宽给 PM，但隐藏写操作
  const { data: identity } = useGetIdentity<AuthUser>();
  const isPM = identity?.role === "project_manager";
  const isAdmin = identity?.role === "admin";

  const [assignOpen, setAssignOpen] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [workOrderOpen, setWorkOrderOpen] = useState(false);
  const [paymentLink, setPaymentLink] = useState<{
    token: string;
    breakdown: PaymentBreakdown;
    sent_to: string;
  } | null>(null);

  const { query } = useOne<CaseDetailResponse>({
    resource: "admin/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  // v0.6.0 — 分配逻辑全部下沉到 AdminAssignDrawer,这里不再拉用户列表 / 调 admin/cases/assign
  const { mutate: sendPaymentLink, mutation: paymentLinkMutation } =
    useCustomMutation();

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  const handleSendPaymentLink = () => {
    if (!detail) return;
    sendPaymentLink(
      {
        url: `admin/cases/${detail.id}/send-payment-link`,
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
        onError: () => alert("生成缴费链接失败，请重试"),
      },
    );
  };

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-[var(--color-danger)] p-8">案件不存在</div>;
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <button
          type="button"
          onClick={() => go({ to: "/admin/cases" })}
          className="ds-btn ds-btn-ghost ds-btn-sm"
          style={{ padding: 0 }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          CRM 案件
        </button>
        <span className="sep">›</span>
        <span className="current">CC-{String(detail.id).padStart(4, "0")}</span>
      </div>

      {/* v1.6.11 — 三栏布局，与 agent/supervisor 详情页统一蓝本 */}
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

        {/* ── 右：sticky 证据状态 + 操作 + 跟进备注 ── */}
        <div
          style={{
            position: "sticky",
            top: 16,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {/* v1.0.0 — 当前催收员小卡片(替代之前显示 user_id) */}
          <div
            className="ds-card"
            style={{
              padding: 12,
              borderLeft: detail.assigned_to
                ? "3px solid var(--color-primary)"
                : "3px solid #E5E7EB",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#6B7280",
                marginBottom: 4,
                fontWeight: 500,
              }}
            >
              当前催收员
            </div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: detail.assigned_to
                  ? "var(--color-neutral-900)"
                  : "#9CA3AF",
              }}
            >
              {detail.assigned_to
                ? (detail.assigned_to_name ?? `user #${detail.assigned_to}`)
                : "未分配 — 在公海"}
            </div>
          </div>

          {/* v0.8.0 Wave C — 证据状态小卡片(admin/PM/supervisor 都看得到) */}
          <EvidenceStatusBadge caseId={detail.id} />

          {!isPM && (
            <div className="ds-card" style={{ padding: 14 }}>
              <div
                style={{
                  fontSize: 12.5,
                  fontWeight: 700,
                  color: "#374151",
                  marginBottom: 10,
                }}
              >
                管理员操作
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  type="button"
                  onClick={handleSendPaymentLink}
                  disabled={paymentLinkMutation.isPending}
                  className="ds-btn ds-btn-primary"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  <CreditCard className="w-3.5 h-3.5" />
                  {paymentLinkMutation.isPending ? "生成中…" : "发送缴费链接"}
                </button>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={() => setAssignOpen(true)}
                    className="ds-btn ds-btn-secondary"
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    <Users className="w-3.5 h-3.5" />
                    分配 / 重分配
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setWorkOrderOpen(true)}
                  className="ds-btn ds-btn-secondary"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  <ClipboardList className="w-3.5 h-3.5" />
                  创建工单
                </button>
                <button
                  type="button"
                  onClick={() => setConvertOpen(true)}
                  className="ds-btn ds-btn-secondary"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    color: "#7e3af2",
                    borderColor: "#c4b5fd",
                  }}
                >
                  <Scale className="w-3.5 h-3.5" />
                  转交法务处理
                </button>
              </div>
            </div>
          )}
          {isPM && (
            <div
              className="ds-card"
              style={{
                background: "#f0f9ff",
                color: "#0369a1",
                padding: "10px 12px",
                fontSize: 12,
                textAlign: "center",
              }}
            >
              项目经理为只读视图，分配 / 工单 / 法务转化由物业管理员处理
            </div>
          )}

          {/* v1.6.11 — 跟进备注移到右栏（操作卡下面，便于操作完直接写） */}
          {!isPM && (
            <FollowUpNoteCard
              caseId={detail.id}
              endpoint={`admin/cases/${detail.id}/stage`}
              invalidateResource="admin/cases"
            />
          )}
        </div>
      </div>

      {/* v0.6.0 — 分配 / 重新分配右弹 Drawer(替换原中间居中 modal) */}
      {assignOpen && (
        <AdminAssignDrawer
          caseIds={[detail.id]}
          ownerName={detail.owner?.name ?? undefined}
          currentAssignedTo={detail.assigned_to ?? null}
          onClose={() => setAssignOpen(false)}
          onAssigned={() => {
            setAssignOpen(false);
            void invalidate({
              resource: "admin/cases",
              invalidates: ["detail", "list"],
              id: detail.id,
            });
          }}
        />
      )}

      {convertOpen && (
        <ConvertToLegalModal
          caseId={detail.id}
          onClose={() => setConvertOpen(false)}
          onSuccess={(orderId) => {
            setConvertOpen(false);
            alert(`法务转化订单 #${orderId} 已创建，等待平台运营撮合律所`);
            go({ to: "/admin/legal-conversion" });
          }}
        />
      )}

      {workOrderOpen && (
        <WorkOrderCreateModal
          caseId={detail.id}
          onClose={() => setWorkOrderOpen(false)}
          onSuccess={(orderId) => {
            setWorkOrderOpen(false);
            alert(`工单 #${orderId ?? "?"} 已创建，已自动派单给协调员`);
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

      {/* unused import keep-alive: Download icon reserved for v1.x 导出账单 */}
      <span style={{ display: "none" }}>
        <Download size={1} />
      </span>
    </div>
  );
}
