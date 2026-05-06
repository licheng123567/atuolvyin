// frontend/src/pages/calls/detail.tsx
import { useCustomMutation, useGetIdentity, useGo, useOne } from "@refinedev/core";
import { AlertTriangle, ArrowLeft, Mic } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { AuthUser } from "../../providers/auth-provider";

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

export interface RiskEntry {
  risk_id: string;
  level: string;
  category: string;
  trigger: string;
  text_snippet: string;
  matched_keywords: string[];
  llm_confidence: number;
  speaker: string;
}

export interface RiskAnnotation {
  risk_id: string;
  level: string;
  category: string;
  trigger: string;
  matched_keywords: string[];
  llm_confidence: number;
}

export function getRiskAnnotationForSegment(
  segmentText: string,
  risks: RiskEntry[]
): RiskAnnotation | null {
  for (const risk of risks) {
    if (risk.text_snippet && segmentText.includes(risk.text_snippet)) {
      return {
        risk_id: risk.risk_id,
        level: risk.level,
        category: risk.category,
        trigger: risk.trigger,
        matched_keywords: risk.matched_keywords,
        llm_confidence: risk.llm_confidence,
      };
    }
  }
  return null;
}

const CAT_LABELS: Record<string, string> = {
  owner_abuse: "业主辱骂",
  owner_threat: "业主威胁",
  agent_violation: "催收员违规",
  agent_minor_misconduct: "轻微不当",
};

interface AnalysisData {
  summary: string | null;
  intent: string | null;
  promise_date: string | null;
  excuse_category: string | null;
  compliance_disclosed: boolean | null;
  risk_keywords: string[] | null;
  confidence: number | null;
  needs_review: boolean;
  key_segments?: {
    risks?: RiskEntry[];
    [key: string]: unknown;
  };
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

function SupervisorReviewSection({ callId }: { callId: number }) {
  const [quality, setQuality] = useState<"good" | "bad" | "needs_improvement" | null>(null);
  const [note, setNote] = useState("");
  const [intentCorrection, setIntentCorrection] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const { mutate, isPending } = useCustomMutation();

  const handleSubmit = () => {
    if (!quality) return;
    mutate(
      {
        url: `supervisor/reviews/${callId}`,
        method: "patch",
        values: {
          quality,
          note: note || null,
          intent_correction: intentCorrection || null,
        },
      },
      { onSuccess: () => setSubmitted(true) },
    );
  };

  return (
    <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5 mt-4">
      <h3 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-3">督导质检打标</h3>
      {submitted ? (
        <div className="text-sm" style={{ color: "#15803d" }}>✓ 已提交</div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
            {(["good", "bad", "needs_improvement"] as const).map((q) => (
              <label key={q} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 14, cursor: "pointer" }}>
                <input
                  type="radio"
                  name={`quality-${callId}`}
                  value={q}
                  checked={quality === q}
                  onChange={() => setQuality(q)}
                />
                {q === "good" ? "优质" : q === "bad" ? "差" : "需改进"}
              </label>
            ))}
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="复核备注（可选）"
            rows={2}
            style={{
              width: "100%",
              padding: "8px 10px",
              border: "1px solid #d1d5db",
              borderRadius: 6,
              fontSize: 13,
              resize: "vertical",
              marginBottom: 8,
              boxSizing: "border-box",
            }}
          />
          <input
            value={intentCorrection}
            onChange={(e) => setIntentCorrection(e.target.value)}
            placeholder="AI 意图修正（可选）"
            style={{
              width: "100%",
              padding: "8px 10px",
              border: "1px solid #d1d5db",
              borderRadius: 6,
              fontSize: 13,
              marginBottom: 12,
              boxSizing: "border-box",
            }}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!quality || isPending}
            style={{
              padding: "6px 16px",
              background: "var(--color-primary)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: !quality || isPending ? "default" : "pointer",
              fontSize: 13,
              opacity: !quality || isPending ? 0.5 : 1,
            }}
          >
            {isPending ? "提交中…" : "提交复核"}
          </button>
        </>
      )}
    </div>
  );
}

export function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const { data: identity } = useGetIdentity<AuthUser>();

  const { query } = useOne<CallDetailData>({
    resource: "calls",
    id: id!,
  });

  const detail = query.data?.data;
  const isLoading = query.isLoading;
  const isReviewer = identity?.role === "supervisor" || identity?.role === "admin";

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
                  detail.transcript.segments.map((seg: TranscriptSegment, i: number) => {
                    const risks = detail.analysis?.key_segments?.risks ?? [];
                    const annotation = getRiskAnnotationForSegment(seg.text, risks);
                    return (
                    <div key={i} className="text-sm">
                      <div className="flex gap-3">
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
                      {annotation && (
                        <p className="mt-1 text-xs text-red-700 bg-red-50 px-2 py-1 rounded flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 shrink-0" />
                          <span>
                            {CAT_LABELS[annotation.category] ?? annotation.category}（{annotation.level}
                            {annotation.matched_keywords.length > 0
                              ? ` · 关键词「${annotation.matched_keywords.slice(0, 2).join("、")}」`
                              : ""}）
                          </span>
                          {annotation.llm_confidence > 0 && (
                            <span className="text-neutral-400 ml-auto">
                              置信度 {(annotation.llm_confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                    );
                  })
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

      {/* Supervisor quality labeling section */}
      {isReviewer && id && (
        <SupervisorReviewSection callId={Number(id)} />
      )}
    </div>
  );
}
