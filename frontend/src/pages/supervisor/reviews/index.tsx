// 1:1 还原 ui/supervisor.html#sv-review 质检复核
import { useList } from "@refinedev/core";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

interface ReviewItemOut {
  call_id: number;
  case_id: number | null;
  callee_phone_masked: string;
  started_at: string | null;
  duration_sec: number | null;
  ai_intent: string | null;
  ai_summary: string | null;
  ai_confidence?: number | null;
  needs_review: boolean;
  supervisor_quality: "good" | "bad" | "needs_improvement" | null;
  supervisor_review_note: string | null;
  supervisor_reviewed_at: string | null;
  agent_name?: string | null;
}

const QUALITY_LABELS: Record<string, string> = {
  good: "已确认",
  bad: "已修正",
  needs_improvement: "需修正",
};

const QUALITY_BADGE_CLASS: Record<string, string> = {
  good: "ds-badge ds-badge-green",
  bad: "ds-badge ds-badge-blue",
  needs_improvement: "ds-badge ds-badge-orange",
};

function formatDuration(sec: number | null): string {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatStartedAt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return d.toTimeString().slice(0, 5);
  }
  const yest = new Date();
  yest.setDate(yest.getDate() - 1);
  if (d.toDateString() === yest.toDateString()) {
    return `昨天 ${d.toTimeString().slice(0, 5)}`;
  }
  const days = Math.floor((today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (days <= 7) return `${days}天前`;
  return d.toISOString().slice(0, 10);
}

export function SupervisorReviewsPage() {
  const [statusFilter, setStatusFilter] = useState<"pending" | "all" | "confirmed" | "fixed">("pending");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const navigate = useNavigate();

  const onlyPending = statusFilter === "pending";
  const { query } = useList<ReviewItemOut>({
    resource: "supervisor/reviews",
    filters: [{ field: "only_pending", operator: "eq", value: onlyPending }],
    pagination: { currentPage: page, pageSize },
  });

  const raw = query.data?.data as unknown;
  const allItems: ReviewItemOut[] = Array.isArray(raw)
    ? (raw as ReviewItemOut[])
    : ((raw as { items?: ReviewItemOut[] } | undefined)?.items ?? []);

  // 前端附加过滤（统一 pending/confirmed/fixed/all 体验）
  let items = allItems;
  if (statusFilter === "confirmed") items = allItems.filter((i) => i.supervisor_quality === "good");
  if (statusFilter === "fixed") items = allItems.filter((i) => i.supervisor_quality === "bad");

  const total = query.data?.total ?? items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">质检复核</h1>
          <div className="page-subtitle">对 AI 自动质检结果进行人工复核与修正</div>
        </div>
        <div className="filters-bar">
          <select
            className="form-control"
            style={{ width: "auto" }}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as typeof statusFilter);
              setPage(1);
            }}
          >
            <option value="pending">待复核</option>
            <option value="all">全部</option>
            <option value="confirmed">已确认</option>
            <option value="fixed">已修正</option>
          </select>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>通话时间</th>
              <th>催收员</th>
              <th>业主电话</th>
              <th>时长</th>
              <th>AI 判断</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  加载中…
                </td>
              </tr>
            )}
            {!query.isLoading && items.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>
                  暂无待复核通话
                </td>
              </tr>
            )}
            {items.map((it) => {
              const isPending = !it.supervisor_quality;
              return (
                <tr key={it.call_id}>
                  <td>{formatStartedAt(it.started_at)}</td>
                  <td>{it.agent_name ?? "—"}</td>
                  <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}>
                    {it.callee_phone_masked}
                  </td>
                  <td>{formatDuration(it.duration_sec)}</td>
                  <td>
                    {it.ai_intent ?? "—"}
                    {it.ai_confidence != null && (
                      <span
                        style={{
                          color: "var(--color-neutral-500)",
                          fontSize: 12,
                          marginLeft: 6,
                        }}
                      >
                        ({it.ai_confidence.toFixed(2)})
                      </span>
                    )}
                  </td>
                  <td>
                    {isPending ? (
                      <span className="ds-badge ds-badge-orange">待复核</span>
                    ) : (
                      <span className={QUALITY_BADGE_CLASS[it.supervisor_quality!]}>
                        {QUALITY_LABELS[it.supervisor_quality!]}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={
                        isPending
                          ? "ds-btn ds-btn-primary ds-btn-sm"
                          : "ds-btn ds-btn-secondary ds-btn-sm"
                      }
                      onClick={() => navigate(`/supervisor/reviews/${it.call_id}`)}
                    >
                      {isPending ? "复核" : "查看"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="ds-pagination">
          <span className="pagination-info">
            共 {total} 条记录
            {totalPages > 1 && `，第 ${page}/${totalPages} 页`}
          </span>
          {totalPages > 1 && (
            <div className="pagination-pages">
              {page > 1 && (
                <div className="page-btn" onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  ‹
                </div>
              )}
              <div className="page-btn active">{page}</div>
              {page < totalPages && (
                <div
                  className="page-btn"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  ›
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
