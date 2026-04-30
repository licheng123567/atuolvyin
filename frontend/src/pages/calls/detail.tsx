// frontend/src/pages/calls/detail.tsx
import { useGo, useOne } from "@refinedev/core";
import { ArrowLeft, Mic } from "lucide-react";
import { useParams } from "react-router-dom";

interface TranscriptSegment {
  speaker: number;
  start_ms: number;
  end_ms: number;
  text: string;
}

interface TranscriptData {
  full_text: string;
  segments: TranscriptSegment[] | null;
  asr_model: string | null;
}

interface AnalysisData {
  summary: string | null;
  intent: string | null;
  promise_date: string | null;
  excuse_category: string | null;
  compliance_disclosed: boolean | null;
  risk_keywords: string[] | null;
  confidence: number | null;
  needs_review: boolean;
}

interface CallDetailData {
  id: number;
  case_id: number | null;
  callee_phone_masked: string;
  started_at: string | null;
  ended_at: string | null;
  duration_sec: number | null;
  recording_url: string | null;
  status: string;
  transcript: TranscriptData | null;
  analysis: AnalysisData | null;
  created_at: string;
}

export function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { query } = useOne<CallDetailData>({
    resource: "calls",
    id: id!,
  });

  const detail = query.data?.data;
  const isLoading = query.isLoading;

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-[var(--color-danger)] p-8">通话记录不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: -1 as unknown as string })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <Mic className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          通话详情
        </h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          {detail.started_at ? new Date(detail.started_at).toLocaleString("zh-CN") : "—"}
          {detail.duration_sec
            ? `  ·  ${Math.floor(detail.duration_sec / 60)}分${detail.duration_sec % 60}秒`
            : ""}
        </span>
      </div>

      {/* Recording player */}
      {detail.recording_url && (
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 mb-4">
          <div className="text-xs font-medium text-[var(--color-neutral-600)] mb-2">录音播放</div>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={detail.recording_url} className="w-full" />
        </div>
      )}

      {detail.status !== "processed" && (
        <div
          className="rounded-lg p-4 mb-4 text-sm"
          style={{ background: "var(--color-neutral-50)", color: "var(--color-neutral-500)" }}
        >
          通话正在处理中（{detail.status}），转写和分析结果即将生成…
        </div>
      )}

      {detail.status === "processed" && (
        <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 340px" }}>
          {/* Transcript */}
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              通话转写
            </h2>
            {detail.transcript ? (
              <div className="space-y-2">
                {detail.transcript.segments ? (
                  detail.transcript.segments.map((seg: TranscriptSegment, i: number) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span
                        className="shrink-0 font-medium w-12"
                        style={{
                          color: seg.speaker === 0
                            ? "var(--color-primary)"
                            : "var(--color-neutral-700)",
                        }}
                      >
                        {seg.speaker === 0 ? "坐席" : "业主"}
                      </span>
                      <span className="text-[var(--color-neutral-700)]">{seg.text}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--color-neutral-700)] whitespace-pre-wrap">
                    {detail.transcript.full_text}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">暂无转写内容</p>
            )}
          </div>

          {/* Analysis */}
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              AI 分析
            </h2>
            {detail.analysis ? (
              <div className="space-y-3 text-sm">
                {detail.analysis.summary && (
                  <div>
                    <div className="text-xs text-[var(--color-neutral-500)] mb-1">摘要</div>
                    <p className="text-[var(--color-neutral-800)]">{detail.analysis.summary}</p>
                  </div>
                )}
                {detail.analysis.intent && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">意图</span>
                    <span className="font-medium">{detail.analysis.intent}</span>
                  </div>
                )}
                {detail.analysis.promise_date && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">承诺缴费日期</span>
                    <span className="font-medium">{detail.analysis.promise_date}</span>
                  </div>
                )}
                {detail.analysis.excuse_category && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">推托类型</span>
                    <span>{detail.analysis.excuse_category}</span>
                  </div>
                )}
                {detail.analysis.confidence != null && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">置信度</span>
                    <span>{(detail.analysis.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                {detail.analysis.risk_keywords && detail.analysis.risk_keywords.length > 0 && (
                  <div>
                    <div className="text-xs text-[var(--color-neutral-500)] mb-1">风险词</div>
                    <div className="flex flex-wrap gap-1">
                      {detail.analysis.risk_keywords.map((kw: string) => (
                        <span
                          key={kw}
                          className="inline-flex px-2 py-0.5 text-xs rounded"
                          style={{
                            background: "var(--color-danger-light)",
                            color: "var(--color-danger)",
                          }}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {detail.analysis.needs_review && (
                  <div
                    className="rounded p-2 text-xs"
                    style={{
                      background: "var(--color-warning-light)",
                      color: "var(--color-warning)",
                    }}
                  >
                    ⚠️ 需要人工复核
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">暂无分析结果</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
