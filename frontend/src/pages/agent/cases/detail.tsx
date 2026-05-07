// frontend/src/pages/agent/cases/detail.tsx
import {
  useCustomMutation,
  useGetIdentity,
  useGo,
  useList,
  useOne,
} from "@refinedev/core";
import { GitBranch, Phone, PhoneOff, Scale } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { CaseCallItem, CaseDetailResponse } from "../../../types/case";
import type { PaginatedResponse } from "../../../types";

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

export function AgentWorkstationPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [selectedCallIdx, setSelectedCallIdx] = useState(0);
  const { data: identity } = useGetIdentity<{ role: string }>();
  const isExternal = identity?.role === "agent_external";

  const { query: listQuery } = useList<CaseDetailResponse>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 50 },
  });

  const rawListData = listQuery.data?.data;
  const cases: CaseDetailResponse[] =
    (rawListData as unknown as PaginatedResponse<CaseDetailResponse>)?.items ??
    (rawListData as CaseDetailResponse[] | undefined) ??
    [];

  const { query: detailQuery } = useOne<CaseDetailResponse>({
    resource: "agent/cases",
    id: id ?? "",
    queryOptions: { enabled: !!id },
  });

  const detail = detailQuery.data?.data;
  const isLoading = detailQuery.isLoading;
  const selectedCall = detail?.calls[selectedCallIdx] ?? null;
  const { mutate: customMutate } = useCustomMutation();

  const handleCreateWorkOrder = () => {
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
        onSuccess: (resp) => {
          const wo = resp.data as { id?: number };
          alert(`工单 #${wo.id ?? "?"} 已创建`);
        },
        onError: (err) => alert(`建工单失败：${err.message}`),
      },
    );
  };

  const handleCaseIntent = (
    action: "transfer_supervisor" | "transfer_legal",
    label: string,
  ) => {
    if (!detail) return;
    customMutate(
      {
        url: `agent/cases/${detail.id}/intent`,
        method: "post",
        values: { action },
      },
      {
        onSuccess: () => alert(`${label} 已记录，等待业务流程接入`),
        onError: (err) => alert(`${label} 失败：${err.message}`),
      },
    );
  };

  return (
    <div
      className="h-[calc(100vh-64px)] overflow-hidden"
      style={{ display: "grid", gridTemplateColumns: "280px 240px 1fr 340px" }}
    >
      {/* col-cases */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-hidden">
        <div className="p-3 border-b border-[var(--color-neutral-200)]">
          <span className="text-sm font-semibold text-[var(--color-neutral-900)]">我的案件</span>
        </div>
        <div className="overflow-y-auto flex-1">
          {cases.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => go({ to: `/agent/cases/${c.id}` })}
              className={`w-full text-left px-3 py-3 border-b border-[var(--color-neutral-100)] text-sm hover:bg-[var(--color-neutral-50)] ${
                String(c.id) === id
                  ? "border-l-2 border-l-[var(--color-primary)] bg-blue-50"
                  : ""
              }`}
            >
              <div className="font-medium text-[var(--color-neutral-900)]">{c.owner.name}</div>
              <div className="text-xs text-[var(--color-neutral-400)] mt-0.5">
                {c.owner.building} {c.owner.room}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* col-profile */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-y-auto p-4">
        {isLoading && (
          <div className="text-sm text-[var(--color-neutral-400)]">加载中…</div>
        )}
        {detail && (
          <>
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mb-3"
              style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
            >
              {detail.owner.name[0]}
            </div>
            <div className="text-sm font-semibold mb-1">{detail.owner.name}</div>
            <div className="text-xs text-[var(--color-neutral-500)] mb-1">
              {[detail.owner.building, detail.owner.room].filter(Boolean).join(" ")}
            </div>
            {detail.project_name && (
              <div className="text-xs text-[var(--color-neutral-400)] mb-3">
                项目：{detail.project_name}
              </div>
            )}
            {/* T2: agent_external guard — never render full phone for external agents */}
            <div className="text-sm font-mono text-[var(--color-primary)] mb-1">
              {isExternal
                ? (detail.owner.phone_masked ?? "—")
                : (detail.owner.phone ?? detail.owner.phone_masked ?? "—")}
            </div>
            {detail.amount_owed && (
              <div
                className="rounded p-3 text-center mb-4"
                style={{ background: "var(--color-danger-light)" }}
              >
                <div className="text-xs text-[var(--color-neutral-400)]">欠费</div>
                <div
                  className="text-xl font-bold"
                  style={{ color: "var(--color-danger)" }}
                >
                  ¥{Number(detail.amount_owed).toLocaleString()}
                </div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  {detail.months_overdue} 个月
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* col-transcript: call tabs + transcript preview */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-hidden">
        <div className="p-3 border-b border-[var(--color-neutral-200)] flex gap-2 overflow-x-auto">
          {detail?.calls.map((call: CaseCallItem, idx: number) => (
            <button
              key={call.id}
              type="button"
              onClick={() => setSelectedCallIdx(idx)}
              className={`shrink-0 px-3 py-1 text-xs rounded-full border ${
                idx === selectedCallIdx
                  ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary-light)]"
                  : "border-[var(--color-neutral-200)] text-[var(--color-neutral-600)]"
              }`}
            >
              通话 {idx + 1}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {!selectedCall && (
            <div className="text-sm text-[var(--color-neutral-400)]">暂无通话记录</div>
          )}
          {selectedCall && selectedCall.status !== "processed" && (
            <div className="text-sm text-[var(--color-neutral-400)]">
              转写处理中（{selectedCall.status}）…
            </div>
          )}
          {selectedCall?.transcript_preview && (
            <p className="text-sm text-[var(--color-neutral-700)] whitespace-pre-wrap leading-relaxed">
              {selectedCall.transcript_preview}
            </p>
          )}
        </div>
      </div>

      {/* col-ai: AI analysis + activity timeline + operation buttons */}
      <div className="flex flex-col overflow-y-auto p-4 gap-6">
        {/* AI analysis */}
        <div>
          <div className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">AI 分析</div>
          {!selectedCall && (
            <div className="text-sm text-[var(--color-neutral-400)]">选择通话查看分析</div>
          )}
          {selectedCall && selectedCall.status === "processed" && (
            <div className="space-y-3 text-sm">
              {selectedCall.result_tag && (
                <div className="flex justify-between">
                  <span className="text-[var(--color-neutral-500)]">意图</span>
                  <span
                    className="inline-flex px-1.5 py-0.5 text-xs rounded font-medium"
                    style={RESULT_TAG_COLORS[selectedCall.result_tag] ?? {}}
                  >
                    {selectedCall.result_tag}
                  </span>
                </div>
              )}
              {selectedCall.confidence != null && (
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-[var(--color-neutral-500)]">置信度</span>
                    <span>{(selectedCall.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-neutral-100)]">
                    <div
                      className="h-1.5 rounded-full"
                      style={{
                        width: `${selectedCall.confidence * 100}%`,
                        background: "var(--color-primary)",
                      }}
                    />
                  </div>
                </div>
              )}
              <button
                type="button"
                onClick={() => go({ to: `/calls/${selectedCall.id}` })}
                className="text-xs text-[var(--color-primary)] hover:underline"
              >
                查看完整 AI 分析 →
              </button>
            </div>
          )}
        </div>

        {/* Activity timeline (T3: 5B.2) */}
        {detail && (
          <div>
            <div className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">活动时间线</div>
            {detail.calls.length === 0 ? (
              <div className="text-sm text-[var(--color-neutral-400)]">暂无活动记录</div>
            ) : (
              <div className="space-y-3">
                {/* Stage placeholder event */}
                <div className="flex items-center gap-2 text-xs text-[var(--color-neutral-500)] border-l-2 border-[var(--color-primary-light)] pl-3">
                  <span>
                    案件创建 · {STAGE_LABELS[detail.stage] ?? detail.stage}
                  </span>
                </div>
                {/* Call timeline entries */}
                {detail.calls.map((call: CaseCallItem) => (
                  <div
                    key={call.id}
                    className="border border-[var(--color-neutral-100)] rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        {call.status === "processed" ? (
                          <Phone className="w-3.5 h-3.5 text-[var(--color-success)]" />
                        ) : (
                          <PhoneOff className="w-3.5 h-3.5 text-[var(--color-neutral-400)]" />
                        )}
                        <span className="text-xs font-medium text-[var(--color-neutral-700)]">
                          {call.duration_sec
                            ? `${Math.floor(call.duration_sec / 60)}分${call.duration_sec % 60}秒`
                            : "—"}
                        </span>
                      </div>
                      <span className="text-xs text-[var(--color-neutral-400)]">
                        {call.started_at
                          ? new Date(call.started_at).toLocaleString("zh-CN")
                          : "—"}
                      </span>
                    </div>
                    {call.result_tag && (
                      <span
                        className="inline-flex px-1.5 py-0.5 text-xs rounded font-medium"
                        style={RESULT_TAG_COLORS[call.result_tag] ?? {}}
                      >
                        {call.result_tag}
                      </span>
                    )}
                    {call.status === "processed" && (
                      <button
                        type="button"
                        onClick={() => go({ to: `/calls/${call.id}` })}
                        className="block text-xs text-[var(--color-primary)] hover:underline mt-1"
                      >
                        完整 AI 分析 →
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Operation buttons — agent_internal only (T3: PRD禁止external操作) */}
        {detail && !isExternal && (
          <div>
            <div className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">操作</div>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleCreateWorkOrder}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
              >
                建工单
              </button>
              <button
                type="button"
                onClick={() => handleCaseIntent("transfer_supervisor", "转主管")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
              >
                <GitBranch className="w-4 h-4" />
                转主管
              </button>
              <button
                type="button"
                onClick={() => handleCaseIntent("transfer_legal", "转法务")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--color-neutral-300)] text-[var(--color-neutral-600)] hover:bg-[var(--color-neutral-50)] transition-colors"
              >
                <Scale className="w-4 h-4" />
                转法务
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
