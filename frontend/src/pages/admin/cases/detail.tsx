// frontend/src/pages/admin/cases/detail.tsx
import { useGo, useOne } from "@refinedev/core";
import { ArrowLeft, Phone, PhoneOff } from "lucide-react";
import { useParams } from "react-router-dom";
import type { CaseCallItem, CaseDetailResponse } from "../../../types/case";

const STAGE_LABELS: Record<string, string> = {
  new: "待处理", in_progress: "处理中", promised: "已承诺",
  paid: "已缴费", escalated: "已上报", closed: "已关闭",
};

const RESULT_TAG_COLORS: Record<string, React.CSSProperties> = {
  "承诺缴": { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  "立即缴": { background: "var(--color-success-light)", color: "var(--color-success)" },
  "推托": { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  "拒缴": { background: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function AdminCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<CaseDetailResponse>({
    resource: "admin/cases",
    id: id!,
  });

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-[var(--color-danger)] p-8">案件不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          案件详情
        </h1>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
        >
          {STAGE_LABELS[detail.stage] ?? detail.stage}
        </span>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "340px 1fr" }}>
        {/* Left column */}
        <div className="space-y-4">
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
        </div>

        {/* Right column — call timeline */}
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            通话记录
          </h2>
          {detail.calls.length === 0 ? (
            <div className="text-sm text-[var(--color-neutral-400)]">暂无通话记录</div>
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
    </div>
  );
}
