// frontend/src/pages/supervisor/reviews/index.tsx
import { useList, useNavigation } from "@refinedev/core";
import { useState } from "react";

interface ReviewItemOut {
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
}

const QUALITY_LABELS: Record<string, string> = {
  good: "优质",
  bad: "差",
  needs_improvement: "需改进",
};

const QUALITY_STYLES: Record<string, { background: string; color: string }> = {
  good: { background: "#dcfce7", color: "#15803d" },
  bad: { background: "#fee2e2", color: "#b91c1c" },
  needs_improvement: { background: "#fef9c3", color: "#92400e" },
};

export function SupervisorReviewsPage() {
  const [onlyPending, setOnlyPending] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { show } = useNavigation();

  const { query } = useList<ReviewItemOut>({
    resource: "supervisor/reviews",
    filters: onlyPending
      ? [{ field: "only_pending", operator: "eq", value: true }]
      : [{ field: "only_pending", operator: "eq", value: false }],
    pagination: { currentPage: page, pageSize },
  });

  const items: ReviewItemOut[] = (query.data?.data as unknown as ReviewItemOut[]) ?? [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleToggle = () => {
    setOnlyPending((v) => !v);
    setPage(1);
  };

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>质检复核工作台</h2>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={onlyPending}
            onChange={handleToggle}
          />
          仅看待复核
        </label>
      </div>

      {/* Table */}
      {query.isLoading ? (
        <div style={{ color: "var(--color-neutral-400)", fontSize: 14, padding: "32px 0" }}>加载中…</div>
      ) : items.length === 0 ? (
        <div style={{ color: "var(--color-neutral-400)", fontSize: 14, padding: "48px 0", textAlign: "center" }}>
          暂无待复核通话
        </div>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
                {["通话时间", "业主电话", "时长", "AI 意图", "AI 摘要", "评级状态", "操作"].map((h) => (
                  <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 500 }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.call_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "10px 12px" }}>
                    {item.started_at ? new Date(item.started_at).toLocaleString("zh-CN") : "—"}
                  </td>
                  <td style={{ padding: "10px 12px", fontFamily: "monospace" }}>
                    {item.callee_phone_masked}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {item.duration_sec != null
                      ? `${Math.floor(item.duration_sec / 60)}分${item.duration_sec % 60}秒`
                      : "—"}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {item.ai_intent ?? "—"}
                  </td>
                  <td style={{ padding: "10px 12px", maxWidth: 200 }}>
                    {item.ai_summary
                      ? `${item.ai_summary.slice(0, 60)}${item.ai_summary.length > 60 ? "…" : ""}`
                      : "—"}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {item.supervisor_quality ? (
                      <span
                        style={{
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: 12,
                          ...QUALITY_STYLES[item.supervisor_quality],
                        }}
                      >
                        {QUALITY_LABELS[item.supervisor_quality]}
                      </span>
                    ) : (
                      <span style={{ fontSize: 12, color: "#9ca3af" }}>未评级</span>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <button
                      onClick={() => show("calls", String(item.call_id))}
                      style={{
                        padding: "4px 10px",
                        background: "var(--color-primary)",
                        color: "#fff",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      复核
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 16, fontSize: 14 }}>
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{
                  padding: "4px 12px",
                  border: "1px solid #d1d5db",
                  borderRadius: 4,
                  background: page === 1 ? "#f9fafb" : "#fff",
                  cursor: page === 1 ? "default" : "pointer",
                  color: page === 1 ? "#9ca3af" : "#374151",
                }}
              >
                上一页
              </button>
              <span style={{ color: "#6b7280" }}>
                第 {page} / {totalPages} 页，共 {total} 条
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{
                  padding: "4px 12px",
                  border: "1px solid #d1d5db",
                  borderRadius: 4,
                  background: page === totalPages ? "#f9fafb" : "#fff",
                  cursor: page === totalPages ? "default" : "pointer",
                  color: page === totalPages ? "#9ca3af" : "#374151",
                }}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
