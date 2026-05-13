// v1.6.4 — 通用排行榜组件
// 默认 Top 10；超过 10 条时底部显示「查看更多 → 共 X 条」链接，避免一次性渲染过长表格。
import { useGo } from "@refinedev/core";
import type { ReactNode } from "react";

export interface LeaderboardColumn {
  key: string;
  label: string;
  align?: "left" | "right";
  width?: number | string;
}

interface Props<T> {
  rows: T[];
  topN?: number;
  columns: LeaderboardColumn[];
  renderRow: (row: T, idx: number) => ReactNode;
  /** 路由 — 点击「查看更多」跳转完整表格；不传则不渲染链接 */
  viewMoreLink?: string;
  emptyText?: string;
  /** 表格外标题（可选） */
  caption?: string;
}

export function LeaderboardTopN<T>({
  rows,
  topN = 10,
  columns,
  renderRow,
  viewMoreLink,
  emptyText = "暂无数据",
  caption,
}: Props<T>) {
  const go = useGo();
  const visible = rows.slice(0, topN);
  const hasMore = rows.length > topN;

  return (
    <div>
      {caption && (
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          {caption}
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: c.align ?? "left",
                    width: c.width,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  style={{
                    textAlign: "center",
                    color: "var(--color-neutral-400)",
                    padding: "16px 0",
                    fontSize: 13,
                  }}
                >
                  {emptyText}
                </td>
              </tr>
            ) : (
              visible.map((row, idx) => renderRow(row, idx))
            )}
          </tbody>
        </table>
      </div>
      {hasMore && viewMoreLink && (
        <div
          style={{
            marginTop: 8,
            textAlign: "right",
            fontSize: 12,
            color: "var(--color-neutral-500)",
          }}
        >
          仅显示前 {topN} 名 ·{" "}
          <button
            type="button"
            onClick={() => go({ to: viewMoreLink })}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-primary)",
              cursor: "pointer",
              padding: 0,
              fontSize: 12,
              textDecoration: "underline",
            }}
          >
            查看更多 → 共 {rows.length} 条
          </button>
        </div>
      )}
      {hasMore && !viewMoreLink && (
        <div
          style={{
            marginTop: 8,
            textAlign: "right",
            fontSize: 12,
            color: "var(--color-neutral-400)",
          }}
        >
          仅显示前 {topN} 名（共 {rows.length} 条）
        </div>
      )}
    </div>
  );
}
