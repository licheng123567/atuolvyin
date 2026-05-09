// 1:1 还原 ui/admin.html#a-case-detail 案件详情
// v1.6.6 — 业主信息 / 项目基本情况 / 活动时间线 抽到 components/case/* 共享给 agent
import { useCustomMutation, useGetIdentity, useGo, useInvalidate, useList, useOne } from "@refinedev/core";
import type { AuthUser } from "../../../providers/auth-provider";
import { ArrowLeft, ClipboardList, CreditCard, Download, Save, Scale, Users } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { UserRole } from "../../../types";
import type { CaseDetailResponse } from "../../../types/case";
import { ConvertToLegalModal } from "../../../components/legal-conversion/ConvertToLegalModal";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { BillBreakdownCard } from "../../../components/case/BillBreakdownCard";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import { STAGE_LABELS } from "../../../components/case/constants";

interface AdminUser {
  id: number;
  name: string;
  role: UserRole;
}

export function AdminCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();

  // v1.4 — PM 角色只读：admin/cases 路由放宽给 PM，但隐藏写操作
  const { data: identity } = useGetIdentity<AuthUser>();
  const isPM =
    identity?.role === "project_manager_property" ||
    identity?.role === "project_manager_provider";

  const [assignOpen, setAssignOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);
  const [convertOpen, setConvertOpen] = useState(false);
  const [followupNote, setFollowupNote] = useState("");
  const [newStage, setNewStage] = useState("");

  const { query } = useOne<CaseDetailResponse>({
    resource: "admin/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const { query: agentsQuery } = useList<AdminUser>({
    resource: "admin/users",
    pagination: { currentPage: 1, pageSize: 100 },
  });

  const agentsRaw = agentsQuery.data?.data;
  const agentsAll: AdminUser[] = Array.isArray(agentsRaw)
    ? (agentsRaw as AdminUser[])
    : ((agentsRaw as unknown as { items?: AdminUser[] })?.items ?? []);
  const agents = agentsAll.filter(
    (u: AdminUser) =>
      u.role === "agent_internal" || u.role === "agent_external",
  );

  const { mutate: assignCase, mutation: assignMutation } = useCustomMutation();
  const assigning = assignMutation.isPending;
  const { mutate: createWorkOrderMutate } = useCustomMutation();
  const { mutate: patchStage } = useCustomMutation();

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  const handleCreateWorkOrder = () => {
    if (!detail) return;
    const description = window.prompt("工单内容（必填）：");
    if (!description?.trim()) return;
    createWorkOrderMutate(
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
        onSuccess: (resp) => {
          const wo = resp.data as { id?: number };
          alert(`工单 #${wo.id ?? "?"} 已创建`);
        },
        onError: (err) => alert(`建工单失败：${err.message}`),
      },
    );
  };

  const handleAssign = () => {
    if (!selectedAgent || !detail) return;
    assignCase(
      {
        url: "admin/cases/assign",
        method: "post",
        values: { case_ids: [detail.id], assign_to: selectedAgent },
      },
      {
        onSuccess: () => {
          setAssignOpen(false);
          setSelectedAgent(null);
          void invalidate({
            resource: "admin/cases",
            invalidates: ["detail", "list"],
            id: detail.id,
          });
        },
        onError: () => alert("分配失败，请重试"),
      },
    );
  };

  const handleSaveFollowup = () => {
    if (!detail || !newStage) return;
    patchStage(
      {
        url: `admin/cases/${detail.id}/stage`,
        method: "patch",
        values: { stage: newStage, note: followupNote },
      },
      {
        onSuccess: () => {
          setFollowupNote("");
          setNewStage("");
          void invalidate({
            resource: "admin/cases",
            invalidates: ["detail"],
            id: detail.id,
          });
        },
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

      <div className="detail-grid">
        {/* Left column */}
        <div>
          <OwnerInfoCard detail={detail} />
          <ProjectInfoCard detail={detail} />
          <BillBreakdownCard detail={detail} />


          {/* operation buttons */}
          {!isPM && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                <CreditCard className="w-3.5 h-3.5" />
                发送缴费链接
              </button>
              <button
                type="button"
                onClick={() => setAssignOpen(true)}
                className="ds-btn ds-btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                <Users className="w-3.5 h-3.5" />
                分配 / 重分配
              </button>
              <button
                type="button"
                onClick={handleCreateWorkOrder}
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
          )}
          {isPM && (
            <div
              style={{
                background: "#f0f9ff",
                color: "#0369a1",
                padding: "10px 12px",
                borderRadius: 6,
                fontSize: 12,
                textAlign: "center",
              }}
            >
              项目经理为只读视图，分配 / 工单 / 法务转化由物业管理员处理
            </div>
          )}
        </div>

        {/* Right column */}
        <div>
          <ActivityTimeline
            calls={detail.calls}
            timelineEvents={detail.timeline_events}
            createdAt={detail.created_at}
          />

          {/* Followup form — PM 只读 */}
          {!isPM && (
          <div className="ds-card">
            <div className="card-header">
              <span className="card-title">添加跟进备注</span>
            </div>
            <div className="card-body">
              <textarea
                className="form-control"
                placeholder="记录本次跟进情况、业主态度、下一步计划..."
                style={{ height: 80 }}
                value={followupNote}
                onChange={(e) => setFollowupNote(e.target.value)}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontSize: 13,
                      color: "#374151",
                      fontWeight: 500,
                    }}
                  >
                    更新阶段：
                  </span>
                  <select
                    className="form-control"
                    style={{ width: 140 }}
                    value={newStage}
                    onChange={(e) => setNewStage(e.target.value)}
                  >
                    <option value="">— 不变更 —</option>
                    {Object.entries(STAGE_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="ds-btn ds-btn-primary"
                  disabled={!newStage}
                  onClick={handleSaveFollowup}
                >
                  <Save className="w-3.5 h-3.5" />
                  保存
                </button>
              </div>
            </div>
          </div>
          )}
        </div>
      </div>

      {/* Assign Modal */}
      {assignOpen && (
        <div className="modal-overlay" onClick={() => setAssignOpen(false)}>
          <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">分配 / 重分配坐席</span>
              <button
                type="button"
                className="modal-close"
                onClick={() => setAssignOpen(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              {agents.length === 0 ? (
                <p className="text-sm text-muted">暂无可用坐席</p>
              ) : (
                <ul style={{ display: "flex", flexDirection: "column", gap: 4, listStyle: "none" }}>
                  {agents.map((agent: AdminUser) => (
                    <li key={agent.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedAgent(agent.id)}
                        style={{
                          width: "100%",
                          textAlign: "left",
                          padding: "8px 12px",
                          fontSize: 13.5,
                          borderRadius: "var(--radius-md)",
                          background:
                            selectedAgent === agent.id
                              ? "var(--color-primary-light)"
                              : "transparent",
                          color:
                            selectedAgent === agent.id
                              ? "var(--color-primary)"
                              : "#374151",
                          fontWeight: selectedAgent === agent.id ? 600 : 400,
                          border: "none",
                          cursor: "pointer",
                        }}
                      >
                        {agent.name}
                        <span
                          style={{ fontSize: 11.5, color: "#9ca3af", marginLeft: 8 }}
                        >
                          ({agent.role === "agent_internal" ? "内部" : "外部"})
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="ds-btn ds-btn-secondary"
                onClick={() => {
                  setAssignOpen(false);
                  setSelectedAgent(null);
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="ds-btn ds-btn-primary"
                onClick={handleAssign}
                disabled={!selectedAgent || assigning}
              >
                {assigning ? "分配中…" : "确认分配"}
              </button>
            </div>
          </div>
        </div>
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

      {/* unused import keep-alive: Download icon reserved for v1.x 导出账单 */}
      <span style={{ display: "none" }}>
        <Download size={1} />
      </span>
    </div>
  );
}
