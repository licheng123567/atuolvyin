// v1.8.0 — 催收员工作台 col-2 业主画像下方「最近通话记录」accordion 列表。
// 点击一条 → inline 展开 transcript 全文 + 内嵌录音播放器；再点收起。
// 简化版（不含工单/法务/系统事件，只有通话），与详情页 ActivityTimeline 区别开。
import { ChevronDown, ChevronRight, Headphones, Phone, PhoneOff } from "lucide-react";
import { useState } from "react";
import type { CaseCallItem } from "../../types/case";
import { RESULT_TAG_BADGE_CLASS, formatDateTime, formatDuration } from "./constants";

interface Props {
  calls: CaseCallItem[];
}

export function RecentCallsAccordion({ calls }: Props) {
  if (calls.length === 0) {
    return (
      <div>
        <div style={{
          fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8,
        }}>最近通话记录</div>
        <div style={{
          fontSize: 12, color: "var(--color-neutral-400)",
          padding: "16px 12px", textAlign: "center",
          background: "var(--color-neutral-50)", borderRadius: 6,
        }}>
          暂无通话记录
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{
        fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8,
      }}>最近通话记录</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {calls.slice(0, 6).map((call) => (
          <CallAccordionRow key={call.id} call={call} />
        ))}
      </div>
    </div>
  );
}

function CallAccordionRow({ call }: { call: CaseCallItem }) {
  const [expanded, setExpanded] = useState(false);
  const isAnswered = (call.duration_sec ?? 0) > 10;
  const hasRecording = !!call.recording_url;
  const isProcessed = call.status === "processed";

  return (
    <div style={{
      border: "1px solid var(--color-neutral-200)",
      borderRadius: 6,
      background: "white",
      fontSize: 12,
    }}>
      {/* 行 header — 永远显示 */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 10px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div style={{
          width: 20, height: 20, borderRadius: "50%",
          background: isAnswered ? "#dbeafe" : "var(--color-neutral-100)",
          color: isAnswered ? "#1A56DB" : "var(--color-neutral-400)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          {isAnswered ? <Phone size={11} /> : <PhoneOff size={11} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 2,
          }}>
            <span style={{ fontWeight: 600, color: "#0f172a" }}>
              {isAnswered ? formatDuration(call.duration_sec) : "无人接听"}
            </span>
            {call.result_tag && (
              <span
                className={RESULT_TAG_BADGE_CLASS[call.result_tag] ?? "ds-badge ds-badge-gray"}
                style={{ fontSize: 10, padding: "1px 6px" }}
              >
                {call.result_tag}
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-neutral-500)" }}>
            {formatDateTime(call.started_at)}
            {call.agent_name && ` · ${call.agent_name}`}
          </div>
        </div>
        {expanded
          ? <ChevronDown size={14} color="var(--color-neutral-400)" />
          : <ChevronRight size={14} color="var(--color-neutral-400)" />
        }
      </button>

      {/* 展开区 — transcript 全文 + 内嵌 audio */}
      {expanded && (
        <div style={{
          padding: "8px 10px 10px 38px",
          borderTop: "1px solid var(--color-neutral-100)",
          background: "var(--color-neutral-50)",
        }}>
          {isProcessed && call.transcript_preview ? (
            <div style={{ color: "#374151", lineHeight: 1.6 }}>
              {call.transcript_preview}
            </div>
          ) : (
            <div style={{ color: "var(--color-neutral-400)", fontStyle: "italic" }}>
              {isAnswered ? "AI 分析中…" : "AI 标注：无效通话"}
            </div>
          )}
          {hasRecording ? (
            <audio
              controls
              preload="none"
              src={call.recording_url ?? ""}
              style={{ width: "100%", marginTop: 8, height: 32 }}
            />
          ) : isAnswered && (
            <div style={{
              marginTop: 8, fontSize: 11,
              color: "var(--color-neutral-400)",
              display: "inline-flex", alignItems: "center", gap: 4,
            }}>
              <Headphones size={11} /> 本通话暂无录音
            </div>
          )}
        </div>
      )}
    </div>
  );
}
