// Sprint 15 — Shared helpers for /super/* pages.

export type ServiceStatus = "ok" | "degraded" | "down";

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1) return "<1 ms";
  return `${ms} ms`;
}

export function getStatusDotColor(status: ServiceStatus | string): string {
  switch (status) {
    case "ok":
      return "bg-green-500";
    case "degraded":
      return "bg-yellow-500";
    case "down":
      return "bg-red-500";
    default:
      return "bg-gray-400";
  }
}

export function formatPercent(
  v: number | null | undefined,
  digits: number = 1,
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}%`;
}

export function formatMinutes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

export function formatPrice(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return "—";
  const num = typeof n === "string" ? Number.parseFloat(n) : n;
  if (Number.isNaN(num)) return "—";
  return `¥${num.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
