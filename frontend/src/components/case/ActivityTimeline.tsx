// v1.6.6 — 活动时间线（admin / agent 详情页 + 催收员工作台 共用）
// v1.6.9 — 工单/法务订单/法务案件节点可跳转详情；其他系统事件可展开看完整 note
// 1:1 还原图 2 右上：通话 + 工单 + 法务转化 + 阶段变更 + 案件创建 等所有沟通事件
import { useGo } from "@refinedev/core";
import { ChevronDown, ChevronRight, ExternalLink, FileText, Phone, PhoneOff, Scale, Upload, Users, Wrench } from "lucide-react";
import { useState } from "react";
import type { CaseCallItem, TimelineEvent } from "../../types/case";
import { RESULT_TAG_BADGE_CLASS, formatDateTime, formatDuration } from "./constants";

interface Props {
  calls: CaseCallItem[];
  timelineEvents: TimelineEvent[];
  createdAt: string;
}

function eventMeta(type: string): { cls: string; title: string; icon: React.ReactNode } {
  switch (type) {
    case "workorder.opened":   return { cls: "tl-system", title: "工单创建",     icon: <Wrench size={11} stroke="white" /> };
    case "workorder.resolved": return { cls: "tl-system", title: "工单处理完成", icon: <Wrench size={11} stroke="white" /> };
    case "legal.converted":    return { cls: "tl-system", title: "转化为法务",   icon: <Scale  size={11} stroke="white" /> };
    case "legal.case":         return { cls: "tl-system", title: "法务跟进",     icon: <Scale  size={11} stroke="white" /> };
    case "case.assigned":      return { cls: "tl-system", title: "案件分配",     icon: <Users  size={11} stroke="white" /> };
    case "case.stage_changed": return { cls: "tl-system", title: "阶段更新",     icon: <FileText size={11} stroke="white" /> };
    case "case.escalated":     return { cls: "tl-system", title: "升级处理",     icon: <FileText size={11} stroke="white" /> };
    case "case.released":      return { cls: "tl-system", title: "释放至公海",   icon: <FileText size={11} stroke="white" /> };
    default:                   return { cls: "tl-system", title: type,           icon: <FileText size={11} stroke="white" /> };
  }
}

export function ActivityTimeline({ calls, timelineEvents, createdAt }: Props) {
  const go = useGo();
  const isEmpty = calls.length === 0 && timelineEvents.filter((e) => e.type !== "call").length === 0;

  return (
    <div className="ds-card">
      <div className="card-header">
        <span className="card-title">活动时间线</span>
      </div>
      <div className="card-body">
        <div className="timeline">
          {/* 通话记录（按时间倒序） v1.6.8 — 整行可点击跳到通话详情 */}
          {calls.map((call, idx) => {
            const isProcessed = call.status === "processed";
            const isAnswered = (call.duration_sec ?? 0) > 10;
            const navigateToCall = () => go({ to: `/calls/${call.id}` });
            return (
              <div
                className="tl-item"
                key={call.id}
                onClick={navigateToCall}
                style={{ cursor: "pointer" }}
                title="点击查看完整通话详情 / 录音 / AI 分析"
              >
                <div className="tl-spine">
                  <div className={`tl-node ${isAnswered ? "tl-call" : "tl-system"}`}>
                    {isAnswered ? <Phone size={11} stroke="white" /> : <PhoneOff size={11} stroke="white" />}
                  </div>
                  {idx < calls.length - 1 && <div className="tl-line" />}
                </div>
                <div className="tl-body">
                  <div className="tl-head">
                    <span className="tl-title">
                      {isAnswered ? `通话 · ${formatDuration(call.duration_sec)}` : "无人接听"}
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
                            className={RESULT_TAG_BADGE_CLASS[call.result_tag] ?? "ds-badge ds-badge-gray"}
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
                      {/* v1.6.7 — E5 inline 录音播放（recording_url 存在时） */}
                      {call.recording_url && (
                        <audio
                          controls
                          preload="none"
                          src={call.recording_url}
                          onClick={(e) => e.stopPropagation()}
                          style={{ width: "100%", marginTop: 8, height: 32 }}
                        />
                      )}
                      <hr className="tl-card-sep" />
                      <div className="tl-card-meta">
                        <span style={{ color: "var(--color-primary)" }}>查看完整 →</span>
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

          {/* 其他活动事件（工单 / 法务 / 阶段 / 分配 / 审计）— v1.6.9 可点击查看详情/展开 */}
          {timelineEvents
            .filter((e) => e.type !== "call")
            .map((e, i) => (
              <SystemEventRow key={`tl-${i}`} event={e} onJump={(to) => go({ to })} />
            ))}

          {/* 案件创建（最早事件）*/}
          <div className="tl-item">
            <div className="tl-spine">
              <div className="tl-node tl-system">
                <Upload size={11} stroke="white" />
              </div>
            </div>
            <div className="tl-body">
              <div className="tl-head">
                <span className="tl-title">案件创建</span>
                <span className="tl-meta">{formatDateTime(createdAt)}</span>
              </div>
              <div className="tl-text">从 Excel 批量导入</div>
            </div>
          </div>

          {isEmpty && (
            <div className="empty-state">
              <div className="empty-title">暂无通话记录</div>
              <div className="empty-desc">坐席发起通话后会在此显示</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * v1.6.9 — 系统事件行，按 target_type 决定行为：
 * - workorder → 整行可点击跳到工单详情
 * - legal_order → 跳到法务订单详情
 * - legal_case → 跳到法务案件详情
 * - 其他（阶段变更/分配/升级/释放）→ 可展开看完整 note + 操作人
 */
function SystemEventRow({
  event,
  onJump,
}: {
  event: TimelineEvent;
  onJump: (to: string) => void;
}) {
  const meta = eventMeta(event.type);
  const [expanded, setExpanded] = useState(false);

  // 决定跳转目标
  let jumpTo: string | null = null;
  if (event.target_id != null) {
    if (event.target_type === "workorder") {
      jumpTo = `/workorder/orders/${event.target_id}`;
    } else if (event.target_type === "legal_order") {
      jumpTo = `/admin/legal-conversion/${event.target_id}`;
    } else if (event.target_type === "legal_case") {
      jumpTo = `/legal/cases/${event.target_id}`;
    }
  }

  const hasJump = jumpTo !== null;
  const isLong = (event.note?.length ?? 0) > 40;
  const canExpand = !hasJump && (isLong || !!event.actor);

  return (
    <div
      className="tl-item"
      onClick={() => {
        if (hasJump && jumpTo) onJump(jumpTo);
        else if (canExpand) setExpanded((v) => !v);
      }}
      style={{ cursor: hasJump || canExpand ? "pointer" : "default" }}
      title={hasJump ? "点击查看详情 →" : canExpand ? "点击展开" : ""}
    >
      <div className="tl-spine">
        <div className={`tl-node ${meta.cls}`}>{meta.icon}</div>
        <div className="tl-line" />
      </div>
      <div className="tl-body">
        <div className="tl-head">
          <span className="tl-title">{meta.title}</span>
          <span className="tl-meta">
            {formatDateTime(event.ts)}
            {event.actor ? ` · ${event.actor}` : ""}
            {hasJump && (
              <ExternalLink
                size={11}
                style={{ marginLeft: 4, verticalAlign: "middle", color: "var(--color-primary)" }}
              />
            )}
            {canExpand && (
              expanded
                ? <ChevronDown size={11} style={{ marginLeft: 4, verticalAlign: "middle", color: "var(--color-neutral-400)" }} />
                : <ChevronRight size={11} style={{ marginLeft: 4, verticalAlign: "middle", color: "var(--color-neutral-400)" }} />
            )}
          </span>
        </div>
        {event.note && (
          <div
            className="tl-text"
            style={{
              whiteSpace: expanded ? "pre-wrap" : "nowrap",
              overflow: expanded ? "visible" : "hidden",
              textOverflow: expanded ? "clip" : "ellipsis",
            }}
          >
            {event.note}
          </div>
        )}
        {expanded && (event.actor || event.target_id != null) && (
          <div style={{
            fontSize: 11, color: "var(--color-neutral-500)", marginTop: 4,
            paddingTop: 4, borderTop: "1px dashed var(--color-neutral-100)",
          }}>
            {event.actor && <span>操作人：{event.actor}</span>}
            {event.target_id != null && (
              <span style={{ marginLeft: event.actor ? 12 : 0 }}>
                ID：#{event.target_id}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
