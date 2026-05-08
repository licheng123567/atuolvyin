// 1:1 还原 ui/admin.html#a-case-detail 案件详情
import { useCustomMutation, useGetIdentity, useGo, useInvalidate, useList, useOne } from "@refinedev/core";
import type { AuthUser } from "../../../providers/auth-provider";
import {
  ArrowLeft,
  ClipboardList,
  CreditCard,
  Download,
  FileText,
  Phone,
  PhoneOff,
  Save,
  Scale,
  Upload,
  Users,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { UserRole } from "../../../types";
import type { CaseCallItem, CaseDetailResponse, TimelineEvent } from "../../../types/case";
import { ConvertToLegalModal } from "../../../components/legal-conversion/ConvertToLegalModal";

const STAGE_LABELS: Record<string, string> = {
  new: "待联系",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级中",
  closed: "已关闭",
};

const STAGE_BADGE_CLASS: Record<string, string> = {
  new: "ds-badge ds-badge-gray",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-orange",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

const RESULT_TAG_BADGE_CLASS: Record<string, string> = {
  承诺缴: "ds-badge ds-badge-orange",
  立即缴: "ds-badge ds-badge-green",
  推托: "ds-badge ds-badge-orange",
  拒缴: "ds-badge ds-badge-red",
};

interface AdminUser {
  id: number;
  name: string;
  role: UserRole;
}

function formatDuration(sec: number | null | undefined): string {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}分${s}秒`;
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

  const room =
    detail.owner.building && detail.owner.room
      ? `${detail.owner.building}${detail.owner.room}`
      : detail.owner.building ?? detail.owner.room ?? "—";

  const monthsOverdue = detail.months_overdue ?? 0;
  const amountOwed = detail.amount_owed ? Number(detail.amount_owed) : 0;
  // v1.6.3 — 不再按月推算；直接展示导入时录入的物业费 + 违约金
  const principalAmount = detail.principal_amount ? Number(detail.principal_amount) : 0;
  const lateFeeAmount = detail.late_fee_amount ? Number(detail.late_fee_amount) : 0;
  const hasBillBreakdown = principalAmount > 0 || lateFeeAmount > 0;

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
          <div className="ds-card section-gap">
            <div className="card-header">
              <span className="card-title">业主信息</span>
              <span className={STAGE_BADGE_CLASS[detail.stage] ?? "ds-badge ds-badge-gray"}>
                {STAGE_LABELS[detail.stage] ?? detail.stage}
              </span>
            </div>
            <div className="card-body">
              {/* avatar + name */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: "50%",
                    background: "#dbeafe",
                    color: "#1A56DB",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 20,
                    fontWeight: 700,
                  }}
                >
                  {detail.owner.name[0]}
                </div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>
                    {detail.owner.name}
                  </div>
                  <div style={{ fontSize: 13, color: "#6b7280" }}>{room}</div>
                </div>
              </div>

              {/* info-grid */}
              <div className="info-grid" style={{ marginBottom: 16 }}>
                <div className="info-item">
                  <div className="info-label">手机号</div>
                  <div
                    className="info-value"
                    style={{ fontFamily: "var(--font-mono, monospace)" }}
                  >
                    {detail.owner.phone_masked}
                  </div>
                </div>
                <div className="info-item">
                  <div className="info-label">所属项目</div>
                  <div className="info-value">{detail.project_name ?? "—"}</div>
                </div>
                <div className="info-item">
                  <div className="info-label">负责员工</div>
                  <div className="info-value">
                    {(() => {
                      const role = detail.assigned_role;
                      if (!detail.assigned_to) {
                        return (
                          <span className="ds-badge ds-badge-gray">
                            未分配
                          </span>
                        );
                      }
                      if (role === "agent_external") {
                        return (
                          <span className="ds-badge ds-badge-purple">
                            服务商负责
                          </span>
                        );
                      }
                      if (role === "agent_internal") {
                        return (
                          <span className="ds-badge ds-badge-green">
                            内勤负责
                          </span>
                        );
                      }
                      return `员工 #${detail.assigned_to}`;
                    })()}
                  </div>
                </div>
              </div>

              {/* v1.6.3 — 累计欠费（保留 hero 卡） */}
              {amountOwed > 0 && (
                <div
                  style={{
                    background: "#fef2f2",
                    borderRadius: 8,
                    padding: 16,
                    textAlign: "center",
                    marginBottom: 16,
                  }}
                >
                  <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>
                    累计欠费
                  </div>
                  <div
                    style={{ fontSize: 32, fontWeight: 700, color: "#e02424" }}
                  >
                    ¥{amountOwed.toLocaleString()}
                  </div>
                  {monthsOverdue > 0 && (
                    <div style={{ fontSize: 12, color: "#6b7280" }}>
                      共 {monthsOverdue} 个月
                    </div>
                  )}
                </div>
              )}

              {/* v1.6.3 — 欠费拆分：物业费 + 违约金 + 总额（不再按月推算） */}
              {hasBillBreakdown && (
                <div style={{ marginBottom: 16 }}>
                  {(detail.bill_period_start || detail.bill_period_end) && (
                    <div style={{ fontSize: 12, color: "var(--color-neutral-500)", marginBottom: 8 }}>
                      账单期：{detail.bill_period_start ?? "—"} ~ {detail.bill_period_end ?? "—"}
                    </div>
                  )}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                    <div style={{ padding: 10, background: "#f9fafb", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>物业费</div>
                      <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>¥{principalAmount.toLocaleString()}</div>
                    </div>
                    <div style={{ padding: 10, background: "#fef3c7", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "#92400e" }}>违约金</div>
                      <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, color: "#92400e" }}>¥{lateFeeAmount.toLocaleString()}</div>
                    </div>
                    <div style={{ padding: 10, background: "#fee2e2", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "#991b1b" }}>欠费总额</div>
                      <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2, color: "#991b1b" }}>¥{amountOwed.toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* v1.6.3 — 欠费理由（导入时录入） */}
              {detail.arrears_reason && (
                <div style={{ marginBottom: 16, padding: "10px 12px", background: "#fffbeb", borderRadius: 6, border: "1px solid #fde68a" }}>
                  <div style={{ fontSize: 11, color: "#92400e", marginBottom: 2 }}>欠费理由</div>
                  <div style={{ fontSize: 13, color: "#78350f" }}>{detail.arrears_reason}</div>
                </div>
              )}

              {/* tags 占位（v1.x 后端 owner.tags 字段上线后启用） */}
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  marginTop: 16,
                  flexWrap: "wrap",
                }}
              >
                {detail.owner.do_not_call && (
                  <span className="ds-badge ds-badge-red">免打扰</span>
                )}
                {(detail.months_overdue ?? 0) >= 12 && (
                  <span className="ds-badge ds-badge-orange">长期欠费</span>
                )}
                {detail.stage === "promised" && (
                  <span className="ds-badge ds-badge-blue">已承诺</span>
                )}
              </div>
            </div>
          </div>

          {/* v1.6.3 — 项目基本情况（合同 + 收费） */}
          {detail.project_info && (
            <div className="ds-card section-gap" style={{ borderLeft: "3px solid #6366f1" }}>
              <div className="card-header">
                <span className="card-title">📁 项目基本情况</span>
                <span className="ds-badge ds-badge-blue" style={{ fontSize: 11 }}>{detail.project_info.name}</span>
              </div>
              <div className="card-body">
                <div className="info-grid">
                  {detail.project_info.charge_rate_text && (
                    <div className="info-item" style={{ gridColumn: "span 2" }}>
                      <div className="info-label">收费标准</div>
                      <div className="info-value" style={{ whiteSpace: "pre-wrap" }}>{detail.project_info.charge_rate_text}</div>
                    </div>
                  )}
                  {detail.project_info.charge_period && (
                    <div className="info-item">
                      <div className="info-label">收费周期</div>
                      <div className="info-value">
                        {{ monthly: "按月", quarterly: "按季", semiannual: "按半年", annual: "按年" }[detail.project_info.charge_period] ?? detail.project_info.charge_period}
                      </div>
                    </div>
                  )}
                  {detail.project_info.contract_type && (
                    <div className="info-item">
                      <div className="info-label">合同类型</div>
                      <div className="info-value">
                        {{ preliminary_service: "前期物业服务合同", elected: "选聘合同", re_elected: "续聘合同", interim_management: "临时管理合同" }[detail.project_info.contract_type] ?? detail.project_info.contract_type}
                      </div>
                    </div>
                  )}
                  {(detail.project_info.contract_start_date || detail.project_info.contract_end_date) && (
                    <div className="info-item" style={{ gridColumn: "span 2" }}>
                      <div className="info-label">合同期</div>
                      <div className="info-value">{detail.project_info.contract_start_date ?? "—"} ~ {detail.project_info.contract_end_date ?? "—"}</div>
                    </div>
                  )}
                  {detail.project_info.contract_attachment_key && (
                    <div className="info-item" style={{ gridColumn: "span 2" }}>
                      <div className="info-label">合同附件</div>
                      <div className="info-value">📎 {detail.project_info.contract_attachment_filename ?? "已上传"}</div>
                    </div>
                  )}
                  {detail.project_info.charge_notes && (
                    <div className="info-item" style={{ gridColumn: "span 2" }}>
                      <div className="info-label">收费备注</div>
                      <div className="info-value" style={{ whiteSpace: "pre-wrap" }}>{detail.project_info.charge_notes}</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* v1.5 — 服务团队（电话团队 + 法务团队）*/}
          {(detail.calling_provider_name || detail.legal_law_firm_name) && (
            <div className="ds-card section-gap">
              <div className="card-header">
                <span className="card-title">
                  <Users className="w-4 h-4" style={{ display: "inline", marginRight: 6, verticalAlign: "-3px" }} />
                  服务团队
                </span>
              </div>
              <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <div className="info-label">电话团队</div>
                  <div className="info-value">
                    {detail.calling_provider_name ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <span className="ds-badge ds-badge-blue">服务商</span>
                        {detail.calling_provider_name}
                      </span>
                    ) : (
                      <span className="text-muted">物业自办（未签约服务商）</span>
                    )}
                  </div>
                </div>
                <div>
                  <div className="info-label">法务团队</div>
                  <div className="info-value">
                    {detail.legal_law_firm_name ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <Scale className="w-3.5 h-3.5" style={{ color: "#7e3af2" }} />
                        <span>{detail.legal_law_firm_name}</span>
                        {detail.legal_lawyer_name && (
                          <span style={{ fontSize: 12, color: "#6b7280" }}>· {detail.legal_lawyer_name}</span>
                        )}
                        {detail.legal_order_status && (
                          <span className="ds-badge ds-badge-purple" style={{ fontSize: 11 }}>
                            {legalStatusLabel(detail.legal_order_status)}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-muted">未转化法务</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

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
          {/* Timeline */}
          <div className="ds-card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <span className="card-title">活动时间线</span>
            </div>
            <div className="card-body">
              <div className="timeline">
                {/* 通话记录（按时间倒序） */}
                {detail.calls.map((call: CaseCallItem, idx) => {
                  const isProcessed = call.status === "processed";
                  const isAnswered = (call.duration_sec ?? 0) > 10;
                  return (
                    <div className="tl-item" key={call.id}>
                      <div className="tl-spine">
                        <div className={`tl-node ${isAnswered ? "tl-call" : "tl-system"}`}>
                          {isAnswered ? (
                            <Phone size={11} stroke="white" />
                          ) : (
                            <PhoneOff size={11} stroke="white" />
                          )}
                        </div>
                        {idx < detail.calls.length - 1 && <div className="tl-line" />}
                      </div>
                      <div className="tl-body">
                        <div className="tl-head">
                          <span className="tl-title">
                            {isAnswered
                              ? `通话 · ${formatDuration(call.duration_sec)}`
                              : "无人接听"}
                          </span>
                          <span className="tl-meta">
                            {formatDateTime(call.started_at)} · {call.agent_name ?? "—"}
                          </span>
                        </div>
                        {isProcessed && call.transcript_preview ? (
                          <div className="tl-card">
                            <div className="tl-card-head">
                              AI 话术摘要
                              {call.result_tag && (
                                <span
                                  className={
                                    RESULT_TAG_BADGE_CLASS[call.result_tag] ??
                                    "ds-badge ds-badge-gray"
                                  }
                                  style={{ fontSize: 11 }}
                                >
                                  {call.result_tag}
                                </span>
                              )}
                              {call.confidence != null && (
                                <span style={{ fontSize: 11, color: "#9ca3af" }}>
                                  置信度 {call.confidence.toFixed(2)}
                                </span>
                              )}
                            </div>
                            <div>{call.transcript_preview}</div>
                            <hr className="tl-card-sep" />
                            <div className="tl-card-meta">
                              <a
                                href="#"
                                onClick={(e) => {
                                  e.preventDefault();
                                  go({ to: `/calls/${call.id}` });
                                }}
                              >
                                查看录音
                              </a>
                              <a
                                href="#"
                                onClick={(e) => {
                                  e.preventDefault();
                                  go({ to: `/calls/${call.id}` });
                                }}
                              >
                                完整 AI 分析
                              </a>
                            </div>
                          </div>
                        ) : (
                          <div className="tl-text">
                            {isAnswered ? "AI 分析中…" : "AI 标注：无效通话"}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* 其他活动（工单 / 法务 / 阶段 / 分配 / 审计） */}
                {detail.timeline_events
                  .filter((e: TimelineEvent) => e.type !== "call")
                  .map((e: TimelineEvent, i: number) => {
                    const meta = renderTimelineEventMeta(e.type);
                    return (
                      <div className="tl-item" key={`tl-${i}`}>
                        <div className="tl-spine">
                          <div className={`tl-node ${meta.cls}`}>{meta.icon}</div>
                          <div className="tl-line" />
                        </div>
                        <div className="tl-body">
                          <div className="tl-head">
                            <span className="tl-title">{meta.title}</span>
                            <span className="tl-meta">
                              {formatDateTime(e.ts)}
                              {e.actor ? ` · ${e.actor}` : ""}
                            </span>
                          </div>
                          {e.note && <div className="tl-text">{e.note}</div>}
                        </div>
                      </div>
                    );
                  })}

                {/* 案件导入（创建事件） */}
                <div className="tl-item">
                  <div className="tl-spine">
                    <div className="tl-node tl-system">
                      <Upload size={11} stroke="white" />
                    </div>
                  </div>
                  <div className="tl-body">
                    <div className="tl-head">
                      <span className="tl-title">案件创建</span>
                      <span className="tl-meta">
                        {formatDateTime(detail.created_at)}
                      </span>
                    </div>
                    <div className="tl-text">从 Excel 批量导入</div>
                  </div>
                </div>

                {detail.calls.length === 0 && (
                  <div className="empty-state">
                    <div className="empty-title">暂无通话记录</div>
                    <div className="empty-desc">坐席发起通话后会在此显示</div>
                  </div>
                )}
              </div>
            </div>
          </div>

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

function legalStatusLabel(status: string): string {
  switch (status) {
    case "pending": return "待撮合";
    case "dispatched": return "已派单";
    case "in_service": return "服务中";
    case "completed": return "已完结";
    default: return status;
  }
}

function renderTimelineEventMeta(type: string): {
  cls: string;
  title: string;
  icon: React.ReactNode;
} {
  switch (type) {
    case "workorder.opened":
      return { cls: "tl-system", title: "工单创建", icon: <Wrench size={11} stroke="white" /> };
    case "workorder.resolved":
      return { cls: "tl-system", title: "工单处理完成", icon: <Wrench size={11} stroke="white" /> };
    case "legal.converted":
      return { cls: "tl-system", title: "转化为法务", icon: <Scale size={11} stroke="white" /> };
    case "legal.case":
      return { cls: "tl-system", title: "法务跟进", icon: <Scale size={11} stroke="white" /> };
    case "case.assigned":
      return { cls: "tl-system", title: "案件分配", icon: <Users size={11} stroke="white" /> };
    case "case.stage_changed":
      return { cls: "tl-system", title: "阶段更新", icon: <FileText size={11} stroke="white" /> };
    case "case.escalated":
      return { cls: "tl-system", title: "升级处理", icon: <FileText size={11} stroke="white" /> };
    case "case.released":
      return { cls: "tl-system", title: "释放至公海", icon: <FileText size={11} stroke="white" /> };
    default:
      return { cls: "tl-system", title: type, icon: <FileText size={11} stroke="white" /> };
  }
}
