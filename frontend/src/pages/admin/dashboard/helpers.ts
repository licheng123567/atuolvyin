// frontend/src/pages/admin/dashboard/helpers.ts

export function formatMinutes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

export function getQuotaWarning(
  used: number,
  total: number | null,
): "ok" | "warn" | "danger" {
  if (total == null) return "ok";
  const ratio = used / total;
  if (ratio >= 1) return "danger";
  if (ratio >= 0.8) return "warn";
  return "ok";
}

export function formatRate(r: number | null | undefined): string {
  if (r === null || r === undefined) return "—";
  return `${(r * 100).toFixed(1)}%`;
}

export function formatCurrency(n: number): string {
  return `¥${n.toLocaleString()}`;
}
