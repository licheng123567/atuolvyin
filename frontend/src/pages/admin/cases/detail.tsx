// frontend/src/pages/admin/cases/detail.tsx
import { useCustomMutation, useGo, useInvalidate, useList, useOne } from "@refinedev/core";
import { ArrowLeft, GitBranch, Phone, PhoneOff, UserRoundSearch } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { UserRole } from "../../../types";
import type { CaseCallItem, CaseDetailResponse } from "../../../types/case";
import { ConvertToLegalModal } from "../../../components/legal-conversion/ConvertToLegalModal";

const STAGE_LABELS: Record<string, string> = {
  new: "待处理",
  in_progress: "处理中",
  promised: "已承诺",
  paid: "已缴费",
  escalated: "已上报",
  closed: "已关闭",
};

const RESULT_TAG_COLORS: Record<string, React.CSSProperties> = {
  "承诺缴": { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  "立即缴": { background: "var(--color-success-light)", color: "var(--color-success)" },
  "推托": { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  "拒缴": { background: "var(--color-danger-light)", color: "var(--color-danger)" },
};

interface AdminUser {
  id: number;
  name: string;
  role: UserRole;
}

export function AdminCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const invalidate = useInvalidate();

  const [assignOpen, setAssignOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);
  const [convertOpen, setConvertOpen] = useState(false);

  const { query } = useOne<CaseDetailResponse>({
    resource: "admin/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const { result: agentsResult } = useList<AdminUser>({
    resource: "admin/users",
    pagination: { pageSize: 100 },
  });

  const agents = (agentsResult.data ?? []).filter(
    (u: AdminUser) => u.role === "agent_internal" || u.role === "agent_external",
  );

  const { mutate: assignCase, mutation: assignMutation } = useCustomMutation();
  const assigning = assignMutation.isPending;

  const detail = query.data?.data;
  const isLoading = query.isLoading;

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
        onError: () => {
          alert("分配失败，请重试");
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

  // Build activity timeline: placeholder stage events + calls (desc order)
  const stageEvents: Array<{ key: string; ts: string; label: string }> = [];
  if (detail.stage !== "new") {
    stageEvents.push({
      key: "created",
      ts: detail.created_at,
      label: `案件创建（${new Date(detail.created_at).toLocaleString("zh-CN")}）`,
    });
  }
  if (detail.stage === "in_progress" || detail.stage === "promised" || detail.stage === "escalated") {
    stageEvents.push({
      key: "in_progress",
      ts: detail.updated_at,
      label: `状态进入"${STAGE_LABELS[detail.stage] ?? detail.stage}"`,
    });
  }

  const perMonth =
    detail.amount_owed && detail.months_overdue && detail.months_overdue > 0
      ? (parseFloat(detail.amount_owed) / detail.months_overdue).toFixed(2)
      : null;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => go({ to: "/admin/cases" })}
            className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">案件详情</h1>
          <span
            className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
            style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
          >
            {STAGE_LABELS[detail.stage] ?? detail.stage}
          </span>
        </div>

        {/* Operation buttons */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setAssignOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] transition-colors"
          >
            <UserRoundSearch className="w-4 h-4" />
            分配/重分配
          </button>
          <button
            type="button"
            onClick={() => setConvertOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
          >
            <GitBranch className="w-4 h-4" />
            转法务
          </button>
          <button
            type="button"
            onClick={() => alert("建工单功能将在 v1.1 上线")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
          >
            建工单
          </button>
        </div>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "340px 1fr" }}>
        {/* Left column */}
        <div className="space-y-4">
          {/* Owner info card */}
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold"
                style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
              >
                {detail.owner.name[0]}
              </div>
              <div>
                <div className="text-base font-semibold">{detail.owner.name}</div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  {[detail.owner.building, detail.owner.room].filter(Boolean).join(" ")}
                </div>
              </div>
            </div>
            <div className="text-sm text-[var(--color-neutral-600)] mb-4">
              {detail.owner.phone_masked}
            </div>
            {detail.amount_owed && (
              <div
                className="rounded-lg p-4 text-center mb-4"
                style={{ background: "var(--color-danger-light)" }}
              >
                <div className="text-xs text-[var(--color-neutral-400)] mb-1">累计欠费</div>
                <div className="text-3xl font-bold" style={{ color: "var(--color-danger)" }}>
                  ¥{Number(detail.amount_owed).toLocaleString()}
                </div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  共 {detail.months_overdue} 个月
                </div>
              </div>
            )}
          </div>

          {/* Overdue detail breakdown */}
          {detail.amount_owed && detail.months_overdue != null && detail.months_overdue > 0 && perMonth && (
            <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4">
              <h4 className="font-semibold text-sm mb-2">欠费明细</h4>
              <div className="text-xs text-[var(--color-neutral-500)] mb-2">
                共 {detail.months_overdue} 个月，平均每月 ¥{perMonth}
              </div>
              {/* v1.1: replace with real billing line items from backend */}
              <ul className="text-sm space-y-1">
                {Array.from({ length: detail.months_overdue }).map((_, i) => (
                  <li key={i} className="flex justify-between">
                    <span className="text-[var(--color-neutral-700)]">第 {i + 1} 期物业费</span>
                    <span className="font-medium">¥{perMonth}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right column — activity timeline + call records */}
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            活动时间线
          </h2>

          {/* Stage-change placeholder events */}
          {stageEvents.length > 0 && (
            <div className="mb-4 space-y-2">
              {stageEvents.map((ev) => (
                <div
                  key={ev.key}
                  className="flex items-center gap-2 text-xs text-[var(--color-neutral-500)] border-l-2 border-[var(--color-primary-light)] pl-3"
                >
                  <span>{ev.label}</span>
                </div>
              ))}
            </div>
          )}

          {/* Call records */}
          {detail.calls.length === 0 && stageEvents.length === 0 ? (
            <div className="text-sm text-[var(--color-neutral-400)]">暂无活动记录</div>
          ) : (
            <div className="space-y-4">
              {detail.calls.map((call: CaseCallItem) => (
                <div
                  key={call.id}
                  className="border border-[var(--color-neutral-100)] rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {call.status === "processed" ? (
                        <Phone className="w-4 h-4 text-[var(--color-success)]" />
                      ) : (
                        <PhoneOff className="w-4 h-4 text-[var(--color-neutral-400)]" />
                      )}
                      <span className="text-sm font-medium">
                        {call.duration_sec
                          ? `${Math.floor(call.duration_sec / 60)}分${call.duration_sec % 60}秒`
                          : "—"}
                      </span>
                    </div>
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {call.started_at
                        ? new Date(call.started_at).toLocaleString("zh-CN")
                        : "—"}{" "}
                      · {call.agent_name}
                    </span>
                  </div>
                  {call.transcript_preview && (
                    <div
                      className="rounded p-3 text-sm mb-2"
                      style={{ background: "var(--color-neutral-50)" }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-[var(--color-neutral-600)]">
                          AI 摘要
                        </span>
                        {call.result_tag && (
                          <span
                            className="inline-flex px-1.5 py-0.5 text-xs rounded font-medium"
                            style={RESULT_TAG_COLORS[call.result_tag] ?? {}}
                          >
                            {call.result_tag}
                          </span>
                        )}
                        {call.confidence != null && (
                          <span className="text-xs text-[var(--color-neutral-400)]">
                            置信度 {call.confidence.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <p className="text-[var(--color-neutral-700)] text-xs">
                        {call.transcript_preview}
                      </p>
                      <div className="flex gap-3 mt-2">
                        <button
                          type="button"
                          onClick={() => go({ to: `/calls/${call.id}` })}
                          className="text-xs text-[var(--color-primary)] hover:underline"
                        >
                          完整 AI 分析
                        </button>
                      </div>
                    </div>
                  )}
                  {call.status !== "processed" && (
                    <div className="text-xs text-[var(--color-neutral-400)]">
                      状态: {call.status}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Assign modal */}
      {assignOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-label="分配案件"
        >
          <div className="bg-white rounded-lg shadow-lg w-80 p-6">
            <h3 className="text-base font-semibold mb-4">分配/重分配坐席</h3>
            {agents.length === 0 ? (
              <div className="text-sm text-[var(--color-neutral-400)] mb-4">
                暂无可用坐席
              </div>
            ) : (
              <ul className="space-y-1 mb-4 max-h-60 overflow-y-auto">
                {agents.map((agent: AdminUser) => (
                  <li key={agent.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedAgent(agent.id)}
                      className={`w-full text-left px-3 py-2 text-sm rounded-md transition-colors ${
                        selectedAgent === agent.id
                          ? "bg-[var(--color-primary-light)] text-[var(--color-primary)] font-medium"
                          : "hover:bg-[var(--color-neutral-50)] text-[var(--color-neutral-700)]"
                      }`}
                    >
                      {agent.name}
                      <span className="ml-2 text-xs text-[var(--color-neutral-400)]">
                        ({agent.role === "agent_internal" ? "内部" : "外部"})
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setAssignOpen(false);
                  setSelectedAgent(null);
                }}
                className="px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)]"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleAssign}
                disabled={!selectedAgent || assigning}
                className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-40"
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
    </div>
  );
}
