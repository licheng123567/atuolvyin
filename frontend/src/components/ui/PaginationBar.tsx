// v1.6.5 — 通用分页器（参考 admin/audit-logs ds-pagination 样式）
//
// 用法：
//   <PaginationBar page={page} pageSize={20} total={total} onPageChange={setPage} />
//
// 行为：
// - total <= pageSize → 不渲染（避免 1 页时占视觉）
// - 中间最多显示 5 页码（… 省略号）
// - 信息条「共 X 条，第 P/N 页」始终显示
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (next: number) => void;
}

export function PaginationBar({ page, pageSize, total, onPageChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  // 简单的「中间 5 页 + 首末页 + 省略号」方案
  const pages: (number | "...")[] = [];
  const window = 2;
  const lo = Math.max(1, page - window);
  const hi = Math.min(totalPages, page + window);
  if (lo > 1) {
    pages.push(1);
    if (lo > 2) pages.push("...");
  }
  for (let i = lo; i <= hi; i++) pages.push(i);
  if (hi < totalPages) {
    if (hi < totalPages - 1) pages.push("...");
    pages.push(totalPages);
  }

  return (
    <div className="ds-pagination">
      <span className="pagination-info">
        共 {total} 条，第 {page}/{totalPages} 页
      </span>
      <div className="pagination-pages">
        <button
          type="button"
          className="page-btn"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="上一页"
          style={{ opacity: page <= 1 ? 0.4 : 1, cursor: page <= 1 ? "not-allowed" : "pointer" }}
        >
          <ChevronLeft size={14} />
        </button>
        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`gap-${i}`} className="page-btn" style={{ cursor: "default" }}>
              …
            </span>
          ) : (
            <button
              type="button"
              key={p}
              className={`page-btn${p === page ? " active" : ""}`}
              onClick={() => onPageChange(p)}
            >
              {p}
            </button>
          ),
        )}
        <button
          type="button"
          className="page-btn"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="下一页"
          style={{
            opacity: page >= totalPages ? 0.4 : 1,
            cursor: page >= totalPages ? "not-allowed" : "pointer",
          }}
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
