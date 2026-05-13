// v2.0 Task 4 — Screen 7：通话记录（Android WebView）
// 1:1 对齐 ui/app-agent.html#app-call-history
// 数据源：
//   GET /api/v1/agent/me/call-history?page&page_size — 列表分页
//   GET /api/v1/agent/me/performance               — 顶部副标题（本月通话量 + 总分钟）
import { useCustom } from "@refinedev/core";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import { resultTagBadge } from "../../../lib/caseStage";
import {
  formatDurationChinese,
  formatShortDateTime,
  formatTotalMinutes,
} from "../../../lib/datetime";

interface CallHistoryItem {
  call_id: number;
  started_at: string | null;
  duration_sec: number | null;
  result_tag: string | null;
  case_id: number | null;
  owner_name: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  has_transcript: boolean;
  has_analysis: boolean;
  recording_url?: string | null;
  score?: number | null;
}

interface AgentPerformance {
  user_id: number;
  name: string;
  year_month: string;
  month_calls: number;
  month_connected: number;
  month_promised_cases: number;
  month_paid_cases: number;
  month_paid_amount: string;
  conversion_rate: number | null;
  minutes_used: number;
  minutes_quota: number | null;
  rank_in_tenant: number;
}

const PAGE_SIZE = 20;

export function MobileCallHistoryPage() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const { query: listQ } = useCustom<PaginatedResponse<CallHistoryItem>>({
    url: "agent/me/call-history",
    method: "get",
    config: { query: { page, page_size: PAGE_SIZE } },
  });
  const { query: perfQ } = useCustom<AgentPerformance>({
    url: "agent/me/performance",
    method: "get",
  });

  const isLoading = listQ.isLoading;
  const items: CallHistoryItem[] = listQ.data?.data?.items ?? [];
  const total = listQ.data?.data?.total ?? 0;
  const perf = perfQ.data?.data;

  const monthCalls = perf?.month_calls ?? 0;
  const minutesUsed = perf?.minutes_used ?? 0;

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div>
      {/* ── 顶部标题 + 副标题（对齐 ui/app-agent.html#app-call-history） ── */}
      <div
        style={{
          background: "white",
          padding: "12px 16px",
          borderBottom: "1px solid #e5e7eb",
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>
          通话记录
        </div>
        <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
          本月共 {monthCalls} 通，累计 {formatTotalMinutes(minutesUsed)}
        </div>
      </div>

      <div style={{ padding: "12px 16px 0" }}>
        {isLoading && (
          <div
            style={{
              padding: 24,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            加载中…
          </div>
        )}
        {!isLoading && items.length === 0 && (
          <div
            style={{
              background: "white",
              padding: 24,
              borderRadius: 10,
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 13,
            }}
          >
            暂无通话记录
          </div>
        )}
        {items.map((it) => {
          const isOpen = expanded.has(it.call_id);
          const badge = resultTagBadge(it.result_tag);
          // 后端 CallHistoryItem 没有 analysis.summary；只有 has_analysis 标志位。
          // PoC：展开态显示 has_analysis ? 占位文案 : "暂无 AI 分析"
          const aiText = it.has_analysis
            ? "已生成 AI 分析。完整摘要请到通话详情查看。"
            : "暂无 AI 分析";
          return (
            <div
              key={it.call_id}
              className={`call-history-item${isOpen ? " expanded" : ""}`}
              onClick={() => toggleExpand(it.call_id)}
              style={{ cursor: "pointer" }}
            >
              <div className="call-history-row1">
                <div className="call-history-name">{it.owner_name ?? "—"}</div>
                <div className="call-history-date">
                  {formatShortDateTime(it.started_at)}
                </div>
              </div>
              <div className="call-history-row2">
                <div className="call-history-duration">
                  时长 {formatDurationChinese(it.duration_sec)}
                </div>
                <span className={badge.cls} style={{ fontSize: 11 }}>
                  {badge.label}
                </span>
              </div>
              <div className="call-history-expand">
                <strong>AI分析:</strong> {aiText}
              </div>
            </div>
          );
        })}

        {/* ── 分页 ── */}
        {!isLoading && items.length > 0 && (
          <div
            style={{
              padding: "16px 0",
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 12,
            }}
          >
            {page * PAGE_SIZE >= total ? (
              <span>已加载全部 {total} 条</span>
            ) : (
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                style={{
                  background: "white",
                  border: "1px solid #d1d5db",
                  borderRadius: 8,
                  padding: "8px 18px",
                  fontSize: 13,
                  color: "#374151",
                  cursor: "pointer",
                }}
              >
                加载更多
              </button>
            )}
          </div>
        )}
      </div>

      {/* 底部 Compose tab bar 留白 */}
      <div style={{ height: 70 }} />
    </div>
  );
}

export default MobileCallHistoryPage;
