// v1.5.7 — 通用 CSV 导出工具（客户端生成 + UTF-8 BOM 兼容 Excel 中文）
export interface CsvColumn<T extends Record<string, unknown>> {
  key: keyof T & string;
  label: string;
}

function escapeCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (s.includes('"') || s.includes(",") || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function exportToCsv<T extends Record<string, unknown>>(
  filename: string,
  columns: CsvColumn<T>[],
  rows: T[],
): void {
  const header = columns.map((c) => escapeCell(c.label)).join(",");
  const body = rows
    .map((r) => columns.map((c) => escapeCell(r[c.key])).join(","))
    .join("\n");
  const csv = `\uFEFF${header}\n${body}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
