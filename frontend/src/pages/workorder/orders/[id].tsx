// v1.9.6 — 工单详情页 三栏改造：与法务详情页范式 1:1 对齐
//   左 320：业主画像 + 项目情况（OwnerInfoCard + ProjectInfoCard，案件存在时）
//   中 1fr：全案活动时间线（ActivityTimeline，案件存在时；否则显示工单描述说明）
//   右 280：sticky 操作（描述/优先级/状态/负责人/处理结果 + 保存）
import { useCustomMutation, useGo, useList, useOne, useUpdate } from "@refinedev/core";
import { ArrowLeft, ClipboardList, MessageSquarePlus, Save } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { ActivityTimeline } from "../../../components/case/ActivityTimeline";
import { OwnerInfoCard } from "../../../components/case/OwnerInfoCard";
import { ProjectInfoCard } from "../../../components/case/ProjectInfoCard";
import type { CaseDetailResponse } from "../../../types/case";
import type { PaginatedResponse, UserRole } from "../../../types";
import {
  WORK_ORDER_PRIORITIES,
  WORK_ORDER_STATUSES,
  formatPriority,
  formatStatus,
  formatType,
  getPriorityColor,
  getStatusColor,
  type WorkOrderPriority,
} from "./helpers";

interface CaseRef {
  id: number;
  stage: string;
  owner_name: string;
  owner_phone_masked: string;
}

interface CallRef {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  result_tag: string | null;
}

interface FollowUp {
  id: number;
  work_order_id: number;
  actor_user_id: number;
  actor_name: string | null;
  occurred_at: string;
  kind: string;
  note: string;
}

interface WorkOrderDetail {
  id: number;
  case_id: number | null;
  call_id: number | null;
  order_type: string;
  description: string;
  assigned_to: number | null;
  status: string;
  priority: string;
  resolution: string | null;
  assignee_name: string | null;
  created_at: string;
  case: CaseRef | null;
  call: CallRef | null;
  follow_ups: FollowUp[];
  // 行内业主/项目（v1.9.7）
  owner_name: string | null;
  owner_room: string | null;
  project_name: string | null;
}

const FOLLOW_UP_KIND_LABEL: Record<string, string> = {
  note: "跟进记录",
  resolution_proposed: "方案建议",
  escalation: "升级",
};

interface AdminUser {
  id: number;
  name: string;
  role: UserRole;
}

interface FormState {
  status: string;
  assigned_to: number | null;
  resolution: string;
  priority: WorkOrderPriority;
}

const ROLE_LABEL: Record<string, string> = {
  admin: "管理员",
  supervisor: "督导",
  agent: "催收员",
  legal: "法务对接人",
  coordinator: "协调员",
  workorder: "协调员",
  project_manager: "项目经理",
  superadmin: "平台超管",
  ops: "平台运营",
};

function detailToForm(detail: WorkOrderDetail): FormState {
  return {
    status: detail.status,
    assigned_to: detail.assigned_to,
    resolution: detail.resolution ?? "",
    priority: (detail.priority as WorkOrderPriority) ?? "normal",
  };
}

export function WorkOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<WorkOrderDetail>({
    resource: "workorders",
    id: id ?? "",
  });
  const detail = query.data?.data;

  // 案件存在时拉全案详情（用于业主画像 + 时间线）
  const { query: caseQuery } = useOne<CaseDetailResponse>({
    resource: "supervisor/cases",
    id: detail?.case_id ?? "",
    queryOptions: { enabled: !!detail?.case_id },
  });
  const caseDetail = caseQuery.data?.data;

  // 负责人下拉
  const { result: usersResult } = useList<AdminUser>({
    resource: "admin/users",
    pagination: { pageSize: 100 },
    queryOptions: { retry: 0 },
  });
  const rawUsers = usersResult.data;
  const users: AdminUser[] =
    (rawUsers as unknown as PaginatedResponse<AdminUser>)?.items ??
    (rawUsers as AdminUser[] | undefined) ??
    [];

  const [overrideForm, setOverrideForm] = useState<FormState | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const form: FormState = overrideForm ?? (detail
    ? detailToForm(detail)
    : { status: "open", assigned_to: null, resolution: "", priority: "normal" });

  const setForm = (next: FormState) => setOverrideForm(next);

  const { mutate: update, mutation: updateMutation } = useUpdate();
  const saving = updateMutation.isPending;
  const { mutate: addFollowUp } = useCustomMutation();

  const [newFollowUpNote, setNewFollowUpNote] = useState("");
  const [followUpKind, setFollowUpKind] = useState<"note" | "resolution_proposed" | "escalation">("note");
  const [followUpSaving, setFollowUpSaving] = useState(false);

  function submitFollowUp() {
    if (!detail || !newFollowUpNote.trim()) return;
    setFollowUpSaving(true);
    addFollowUp(
      {
        url: `workorders/${detail.id}/follow-ups`,
        method: "post",
        values: { kind: followUpKind, note: newFollowUpNote.trim() },
      },
      {
        onSuccess: () => {
          setNewFollowUpNote("");
          setFollowUpKind("note");
          setFollowUpSaving(false);
          query.refetch();
        },
        onError: (err) => {
          setFollowUpSaving(false);
          alert(`保存跟进失败：${(err as { message?: string }).message ?? "未知错误"}`);
        },
      },
    );
  }

  const handleSave = () => {
    if (!detail) return;
    setErrorMsg("");
    update(
      {
        resource: "workorders",
        id: detail.id,
        values: {
          status: form.status,
          assigned_to: form.assigned_to,
          resolution: form.resolution || null,
          priority: form.priority,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setOverrideForm(null);
          query.refetch();
        },
        onError: (err) => {
          const e = err as { message?: string };
          setErrorMsg(e.message ?? "保存失败");
        },
      },
    );
  };

  if (query.isLoading) return <div style={{ padding: 32, color: "var(--color-neutral-400)" }}>加载中…</div>;
  if (!detail) return <div style={{ padding: 32, color: "var(--color-danger)" }}>工单不存在</div>;

  return (
    <div>
      <div className="breadcrumb">
        <button type="button" onClick={() => go({ to: "/workorder/orders" })} className="ds-btn ds-btn-ghost ds-btn-sm" style={{ padding: 0 }}>
          <ArrowLeft className="w-3.5 h-3.5" /> 返回
        </button>
        <span className="sep">›</span>
        <span className="current">工单 #{detail.id}</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <ClipboardList className="w-5 h-5" style={{ color: "var(--color-primary)" }} />
        <h1 className="page-title" style={{ marginBottom: 0 }}>工单 #{detail.id}</h1>
        <span style={{ ...getStatusColor(detail.status), padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 500 }}>
          {formatStatus(detail.status)}
        </span>
        <span style={{ ...getPriorityColor(detail.priority), padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 500 }}>
          {formatPriority(detail.priority)}
        </span>
        <span style={{ marginLeft: 8, fontSize: 12, color: "var(--color-neutral-500)" }}>
          类型：{formatType(detail.order_type)}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px minmax(0, 1fr) 320px", gap: 16, alignItems: "start" }}>
        {/* ── 左：业主画像 + 项目情况 ── */}
        <div>
          {caseDetail ? (
            <>
              <OwnerInfoCard detail={caseDetail} />
              <ProjectInfoCard detail={caseDetail} />
            </>
          ) : detail.case_id ? (
            <div className="ds-card">
              <div className="card-body" style={{ color: "var(--color-neutral-400)", padding: 24, textAlign: "center" }}>加载业主画像…</div>
            </div>
          ) : (
            <div className="ds-card">
              <div className="card-header"><span className="card-title">工单信息</span></div>
              <div className="card-body">
                <div className="info-label">类型</div>
                <div className="info-value" style={{ marginBottom: 10 }}>{formatType(detail.order_type)}</div>
                <div className="info-label">创建时间</div>
                <div className="info-value" style={{ fontSize: 12 }}>{new Date(detail.created_at).toLocaleString("zh-CN")}</div>
                <hr style={{ margin: "12px 0", border: "none", borderTop: "1px solid var(--color-neutral-200)" }} />
                <div style={{ fontSize: 12, color: "var(--color-neutral-500)" }}>此工单未关联具体案件</div>
              </div>
            </div>
          )}
        </div>

        {/* ── 中：全案活动时间线（含通话 + 工单 + 法务事件聚合）+ 工单跟进记录卡 ── */}
        <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
          {caseDetail ? (
            <ActivityTimeline
              calls={caseDetail.calls ?? []}
              timelineEvents={caseDetail.timeline_events ?? []}
              createdAt={caseDetail.created_at}
            />
          ) : detail.case_id ? (
            <div className="ds-card">
              <div className="card-body" style={{ color: "var(--color-neutral-400)", padding: 24, textAlign: "center" }}>加载活动时间线…</div>
            </div>
          ) : (
            <div className="ds-card">
              <div className="card-header"><span className="card-title">工单上下文</span></div>
              <div className="card-body">
                <div style={{ whiteSpace: "pre-wrap", color: "var(--color-neutral-700)", lineHeight: 1.7 }}>
                  此工单未关联具体案件。工单原因见右侧。
                </div>
                {detail.call_id && detail.call && (
                  <>
                    <hr style={{ margin: "12px 0", border: "none", borderTop: "1px solid var(--color-neutral-200)" }} />
                    <div className="info-label">关联通话</div>
                    <div className="info-value" style={{ fontSize: 12 }}>
                      {detail.call.started_at ? new Date(detail.call.started_at).toLocaleString("zh-CN") : "—"}
                      {" · "}{detail.call.duration_sec ?? "—"} 秒
                      {" · "}结果：{detail.call.result_tag ?? "—"}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* v1.9.7 — 工单跟进记录卡（写入后自动广播到案件活动时间线）*/}
          <div className="ds-card">
            <div className="card-header"><span className="card-title">工单跟进记录（{detail.follow_ups.length}）</span></div>
            <div className="card-body">
              {detail.follow_ups.length === 0 ? (
                <div style={{ padding: 12, fontSize: 12, color: "var(--color-neutral-500)" }}>
                  暂无跟进记录。处理过程中可在下方添加，写入后会同步到案件活动时间线，督导/管理员/催收员都能看到。
                </div>
              ) : (
                <div className="timeline" style={{ marginBottom: 12 }}>
                  {detail.follow_ups.map((f) => (
                    <div key={f.id} className="tl-item">
                      <div className="tl-spine">
                        <div className="tl-node tl-system"><MessageSquarePlus size={11} stroke="white" /></div>
                      </div>
                      <div className="tl-body">
                        <div className="tl-head">
                          <span className="tl-title">{FOLLOW_UP_KIND_LABEL[f.kind] ?? f.kind}</span>
                          <span className="tl-meta">
                            {new Date(f.occurred_at).toLocaleString("zh-CN")}
                            {f.actor_name && ` · ${f.actor_name}`}
                          </span>
                        </div>
                        <div className="tl-text">{f.note}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {detail.status !== "closed" && (
                <div style={{ borderTop: "1px solid var(--color-neutral-100)", paddingTop: 12, marginTop: 4 }}>
                  <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                    <select
                      className="form-control"
                      style={{ width: 130 }}
                      value={followUpKind}
                      onChange={(e) => setFollowUpKind(e.target.value as "note" | "resolution_proposed" | "escalation")}
                    >
                      <option value="note">跟进记录</option>
                      <option value="resolution_proposed">方案建议</option>
                      <option value="escalation">升级</option>
                    </select>
                  </div>
                  <textarea
                    className="form-control"
                    style={{ height: 70 }}
                    placeholder="例：已联系维保单位，预计明天上门检修；业主同意延后 3 天处理…"
                    value={newFollowUpNote}
                    onChange={(e) => setNewFollowUpNote(e.target.value)}
                  />
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                    <button
                      type="button"
                      className="ds-btn ds-btn-primary ds-btn-sm"
                      disabled={!newFollowUpNote.trim() || followUpSaving}
                      onClick={submitFollowUp}
                    >
                      <MessageSquarePlus className="w-3 h-3" /> {followUpSaving ? "保存中…" : "添加跟进"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── 右：sticky 操作栏 ── */}
        <div style={{ position: "sticky", top: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="ds-card">
            <div className="card-header"><span className="card-title">处理工单</span></div>
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* v1.9.7 — 工单原因创建后只读（审计基线） */}
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">工单原因（创建时记录）</label>
                <div style={{ padding: "8px 12px", background: "#f9fafb", border: "1px solid var(--color-neutral-200)", borderRadius: 6, fontSize: 13, color: "var(--color-neutral-700)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                  {detail.description}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">状态</label>
                  <select
                    className="form-control"
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                  >
                    {WORK_ORDER_STATUSES.map((s) => (
                      <option key={s} value={s}>{formatStatus(s)}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">优先级</label>
                  <select
                    className="form-control"
                    value={form.priority}
                    onChange={(e) => setForm({ ...form, priority: e.target.value as WorkOrderPriority })}
                  >
                    {WORK_ORDER_PRIORITIES.map((p) => (
                      <option key={p} value={p}>{formatPriority(p)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">负责人</label>
                <select
                  className="form-control"
                  value={form.assigned_to ?? ""}
                  onChange={(e) => setForm({ ...form, assigned_to: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">未分配</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}（{ROLE_LABEL[u.role] ?? u.role}）</option>
                  ))}
                  {form.assigned_to !== null && !users.some((u) => u.id === form.assigned_to) && (
                    <option value={form.assigned_to}>用户 #{form.assigned_to} ({detail.assignee_name ?? "未知"})</option>
                  )}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">处理结果 / 解决方案</label>
                <textarea
                  className="form-control"
                  style={{ height: 110 }}
                  placeholder="处理过程、解决方案、跟进结果"
                  value={form.resolution}
                  onChange={(e) => setForm({ ...form, resolution: e.target.value })}
                />
              </div>

              {errorMsg && (
                <div style={{ fontSize: 12, color: "var(--color-danger)" }}>{errorMsg}</div>
              )}

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                {savedAt ? (
                  <span style={{ fontSize: 11, color: "var(--color-success, #16a34a)" }}>已保存（{savedAt}）</span>
                ) : <span />}
                <button
                  type="button"
                  className="ds-btn ds-btn-primary"
                  onClick={handleSave}
                  disabled={saving}
                >
                  <Save className="w-3.5 h-3.5" /> {saving ? "保存中…" : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
