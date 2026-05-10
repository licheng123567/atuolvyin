// 督导侧案件详情 — v1.6.9
// 重写：复用 admin/agent 同款 build_case_detail_response 后端 + 共享组件
// 三栏布局（与 agent 详情页一致）：左 业主+项目+欠费 / 中 时间线+备注 / 右 sticky 操作
import { useGetIdentity, useOne } from "@refinedev/core";
import {
  ArrowLeft,
  BadgePercent,
  Eye,
  Headphones,
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
import type { AuthUser } from "../../../providers/auth-provider";
import type { CaseDetailResponse } from "../../../types/case";

export function SupervisorCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: identity } = useGetIdentity<AuthUser>();
  const [showDiscountModal, setShowDiscountModal] = useState(false);

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
    identity?.role === "platform_super";

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
                  title="发起减免/分期/违约金减免，按金额自动判定走督导/admin 审批"
                >
                  <BadgePercent className="w-3.5 h-3.5" />
                  发起减免
                </button>
              )}
              {detail.assigned_to && (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => alert("已通知催收员介入；下一通通话督导可监听/接管")}
                  title="标记为督导陪同：催收员下次拨打时督导收到通知"
                >
                  <Headphones className="w-3.5 h-3.5" />
                  介入处理
                </button>
              )}
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => navigate("/supervisor/legal-conversion-approvals")}
                title="去「法务转化审批」inbox 处理本案件相关的转法务申请"
              >
                <Scale className="w-3.5 h-3.5" />
                法务转化审批
              </button>
              {detail.assigned_to && (
                <button
                  type="button"
                  className="ds-btn ds-btn-secondary"
                  style={{ width: "100%", justifyContent: "center" }}
                  onClick={() => alert("重新分配功能待接入：督导可指定其他催收员或退回公海")}
                >
                  <Users className="w-3.5 h-3.5" />
                  重新分配
                </button>
              )}
              <button
                type="button"
                className="ds-btn ds-btn-ghost"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => navigate(`/calls/?case_id=${detail.id}`)}
                title="查看本案件所有通话明细"
              >
                <Phone className="w-3.5 h-3.5" />
                通话历史
              </button>
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
    </div>
  );
}
