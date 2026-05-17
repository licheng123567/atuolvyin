// §9.1 — 法务列表页共享的表格状态行（加载中 / 加载失败 / 空态）
import type { ReactNode } from "react";

export function TableStateRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        style={{ textAlign: "center", padding: 32, color: "var(--color-neutral-400)" }}
      >
        {children}
      </td>
    </tr>
  );
}
