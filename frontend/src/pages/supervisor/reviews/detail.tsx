// Sprint 12.2 — 督导复核工作台详情页（PRD §L405）
// 含录音播放器 / 转写 / 风控时间点跳转 / 打标 + 改进建议
import { useCustom, useCustomMutation, useGo } from "@refinedev/core";
import { AlertTriangle, ArrowLeft, ClipboardCheck, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

interface TranscriptSegment {
  speaker: string | null;
  start_ms: number | null;
  end_ms: number | null;
  text: string | null;
}

interface RiskEvent {
  id: number;
  level: string;
  category: string;
  intervention: string;
  trigger_text: string | null;
  audio_offset_ms: number | null;
  occurred_at: string;
}

interface ReviewDetail {
  call_id: number;
  case_id: number | null;
  callee_phone_masked: string;
  started_at: string | null;
  duration_sec: number | null;
  ai_intent: string | null;
  ai_summary: string | null;
  needs_review: boolean;
  supervisor_quality: "good" | "bad" | "needs_improvement" | null;
  supervisor_review_note: string | null;
  supervisor_reviewed_at: string | null;
  recording_url: string | null;
  transcript_text: string | null;
  transcript_segments: TranscriptSegment[];
  risk_events: RiskEvent[];
  asr_model: string | null;
}

const RISK_BADGE: Record<string, { bg: string; color: string }> = {
  L1: { bg: "var(--color-warning-light)", color: "var(--color-warning)" },
  L2: { bg: "var(--color-warning-light)", color: "#a16207" },
  L3: { bg: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function SupervisorReviewDetailPage() {
  const { call_id } = useParams<{ call_id: string }>();
  const callId = Number(call_id);
  const go = useGo();
  const audioRef = useRef<HTMLAudioElement>(null);

  const { query } = useCustom<ReviewDetail>({
    url: `supervisor/reviews/${callId}`,
    method: "get",
  });
  const detail = query.data?.data;

  const { mutate: patch, mutation } = useCustomMutation();
  const [quality, setQuality] = useState<string>("");
  const [note, setNote] = useState("");
  const [intent, setIntent] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const initRef = useRef(false);
  useEffect(() => {
    if (detail && !initRef.current) {
      initRef.current = true;
      setQuality(detail.supervisor_quality ?? "");
      setNote(detail.supervisor_review_note ?? "");
      setIntent(detail.ai_intent ?? "");
    }
  }, [detail]);

  const seekTo = (ms: number | null) => {
    if (ms !== null && audioRef.current) {
      audioRef.current.currentTime = ms / 1000;
      audioRef.current.play().catch(() => undefined);
    }
  };

  const handleLabel = () => {
    if (!detail || !quality) return;
    patch(
      {
        url: `supervisor/reviews/${callId}`,
        method: "patch",
        values: {
          quality,
          note: note || null,
          intent_correction: intent || null,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          query.refetch();
        },
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }
  if (!detail) {
    return <div className="p-6 text-red-600">复核条目不存在</div>;
  }

  return (
    <div className="p-6 space-y-5">
      <button
        type="button"
        onClick={() => go({ to: "/supervisor/reviews" })}
        className="flex items-center gap-1 text-sm text-[var(--color-neutral-500)] hover:text-[var(--color-primary)]"
      >
        <ArrowLeft className="w-4 h-4" /> 返回质检复核列表
      </button>

      <div className="flex items-center gap-2">
        <ClipboardCheck className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">复核 #{detail.call_id}</h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          · {detail.callee_phone_masked} · {detail.duration_sec ?? "—"}s
        </span>
      </div>

      <section
        className="bg-white p-4 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <h2 className="text-sm font-semibold mb-2">录音播放</h2>
        {detail.recording_url ? (
          <audio ref={audioRef} controls src={detail.recording_url} className="w-full">
            您的浏览器不支持 audio 标签
          </audio>
        ) : (
          <p className="text-sm text-[var(--color-neutral-400)]">该通话未上传录音</p>
        )}
      </section>

      {detail.risk_events.length > 0 && (
        <section
          className="bg-white p-4 border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-[var(--color-danger)]" />
            <h2 className="text-sm font-semibold">风控时间点（点击跳转播放）</h2>
          </div>
          <ul className="space-y-1">
            {detail.risk_events.map((r) => {
              const badge = RISK_BADGE[r.level] ?? RISK_BADGE.L1;
              return (
                <li
                  key={r.id}
                  className="flex items-center gap-3 px-2 py-1.5 hover:bg-[var(--color-neutral-50)] cursor-pointer text-sm"
                  onClick={() => seekTo(r.audio_offset_ms)}
                >
                  <span
                    className="px-2 py-0.5 text-xs rounded-full font-medium"
                    style={{ background: badge.bg, color: badge.color }}
                  >
                    {r.level}
                  </span>
                  <span className="text-[var(--color-neutral-600)]">{r.category}</span>
                  <span className="text-[var(--color-neutral-400)]">
                    @{((r.audio_offset_ms ?? 0) / 1000).toFixed(1)}s
                  </span>
                  <span className="text-[var(--color-neutral-700)] flex-1 truncate">
                    {r.trigger_text}
                  </span>
                  <span className="text-xs text-[var(--color-neutral-400)]">
                    {r.intervention}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {detail.transcript_segments.length > 0 && (
        <section
          className="bg-white p-4 border border-[var(--color-neutral-200)]"
          style={{ borderRadius: "var(--radius-lg)" }}
        >
          <h2 className="text-sm font-semibold mb-2">对话转写</h2>
          <ul className="space-y-1.5 text-sm max-h-[320px] overflow-y-auto">
            {detail.transcript_segments.map((s, i) => (
              <li
                key={i}
                className="flex gap-3 cursor-pointer hover:bg-[var(--color-neutral-50)] px-2 py-1 rounded"
                onClick={() => seekTo(s.start_ms ?? null)}
              >
                <span className="w-12 text-xs text-[var(--color-neutral-400)]">
                  {((s.start_ms ?? 0) / 1000).toFixed(1)}s
                </span>
                <span
                  className="w-16 text-xs"
                  style={{
                    color:
                      s.speaker === "agent"
                        ? "var(--color-primary)"
                        : "var(--color-neutral-700)",
                  }}
                >
                  {s.speaker === "agent" ? "坐席" : s.speaker === "owner" ? "业主" : s.speaker}
                </span>
                <span className="flex-1 text-[var(--color-neutral-700)]">{s.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section
        className="bg-white p-4 border border-[var(--color-neutral-200)]"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <h2 className="text-sm font-semibold mb-3">质检打标</h2>
        <div className="grid grid-cols-2 gap-4 max-w-2xl">
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              质量评级
            </label>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            >
              <option value="">— 请选择 —</option>
              <option value="good">优质</option>
              <option value="needs_improvement">需改进</option>
              <option value="bad">差</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
              修正 AI 意图（可选）
            </label>
            <input
              type="text"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder={detail.ai_intent ?? "原 AI 意图为空"}
              className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
              style={{ borderRadius: "var(--radius-md)" }}
            />
          </div>
        </div>
        <div className="mt-3 max-w-2xl">
          <label className="block text-sm text-[var(--color-neutral-600)] mb-1">
            改进建议
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="请描述本通话的具体问题或改进点"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
        <div className="mt-3 flex items-center gap-3 max-w-2xl">
          <button
            type="button"
            disabled={!quality || mutation.isPending}
            onClick={handleLabel}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{
              background: "var(--color-primary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <Save className="w-4 h-4" />
            {mutation.isPending ? "保存中…" : "保存复核"}
          </button>
          {savedAt && (
            <span className="text-xs text-[var(--color-success)]">
              已保存 ({savedAt})
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
