// frontend/src/pages/agent/cases/detail.tsx
import { useGo, useList, useOne } from "@refinedev/core";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { CaseCallItem, CaseDetailResponse } from "../../../types/case";
import type { PaginatedResponse } from "../../../types";

export function AgentWorkstationPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [selectedCallIdx, setSelectedCallIdx] = useState(0);

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
    id: id!,
  });

  const detail = detailQuery.data?.data;
  const isLoading = detailQuery.isLoading;
  const selectedCall = detail?.calls[selectedCallIdx] ?? null;

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
            <div className="text-xs text-[var(--color-neutral-500)] mb-3">
              {[detail.owner.building, detail.owner.room].filter(Boolean).join(" ")}
            </div>
            {detail.owner.phone && (
              <div className="text-sm font-mono text-[var(--color-primary)] mb-1">
                {detail.owner.phone}
              </div>
            )}
            <div className="text-xs text-[var(--color-neutral-400)] mb-4">
              {detail.owner.phone_masked}
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

      {/* col-transcript */}
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

      {/* col-ai */}
      <div className="flex flex-col overflow-y-auto p-4">
        <div className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">AI 分析</div>
        {!selectedCall && (
          <div className="text-sm text-[var(--color-neutral-400)]">选择通话查看分析</div>
        )}
        {selectedCall && selectedCall.status === "processed" && (
          <div className="space-y-3 text-sm">
            {selectedCall.result_tag && (
              <div className="flex justify-between">
                <span className="text-[var(--color-neutral-500)]">意图</span>
                <span className="font-medium">{selectedCall.result_tag}</span>
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
    </div>
  );
}
