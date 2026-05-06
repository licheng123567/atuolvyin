// frontend/src/pages/admin/settlements/helpers.ts
//
// Pure helpers for settlement list & detail pages. Kept side-effect-free so
// they can be unit-tested without React context.

export type SettlementStatus = "DRAFT" | "CONFIRMED" | "PAID" | "DISPUTED";

export interface ActionButton {
  label: string;
  action: "confirm" | "pay" | "dispute";
  variant: "primary" | "secondary" | "danger";
}

export const STATUS_LABELS: Record<SettlementStatus, string> = {
  DRAFT: "草稿",
  CONFIRMED: "已确认",
  PAID: "已支付",
  DISPUTED: "争议中",
};

/**
 * Format the (period_start, period_end) pair as a YYYY-MM string,
 * derived from period_start. Returns "—" when start is invalid.
 * `end` is currently unused — kept in the signature so callers remain
 * symmetric and we can switch to a `start ~ end` rendering later.
 */
export function formatPeriod(start: string, end: string): string {
  void end;
  if (!start) return "—";
  const d = new Date(start);
  if (Number.isNaN(d.getTime())) return "—";
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

/**
 * Tailwind class for a status badge. DRAFT=gray, CONFIRMED=blue,
 * PAID=green, DISPUTED=red. Unknown statuses fall back to neutral.
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case "DRAFT":
      return "bg-gray-100 text-gray-700";
    case "CONFIRMED":
      return "bg-blue-100 text-blue-700";
    case "PAID":
      return "bg-green-100 text-green-700";
    case "DISPUTED":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

/**
 * Format an amount (number or numeric string) as "¥12,345.67". Falls back
 * to "¥0.00" for invalid input.
 */
export function formatAmount(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return "¥0.00";
  const num = typeof n === "string" ? Number(n) : n;
  if (!Number.isFinite(num)) return "¥0.00";
  return `¥${num.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Available actions for a given statement status.
 * - DRAFT: confirm + dispute
 * - CONFIRMED: pay + dispute
 * - PAID: none
 * - DISPUTED: none (re-confirm flow not implemented in this sprint)
 */
export function getActionButtons(status: string): ActionButton[] {
  switch (status) {
    case "DRAFT":
      return [
        { label: "确认结算单", action: "confirm", variant: "primary" },
        { label: "发起争议", action: "dispute", variant: "danger" },
      ];
    case "CONFIRMED":
      return [
        { label: "标记已支付", action: "pay", variant: "primary" },
        { label: "发起争议", action: "dispute", variant: "danger" },
      ];
    default:
      return [];
  }
}

/**
 * Returns the last `n` year-month options as YYYY-MM strings, newest first.
 */
export function recentYearMonths(n: number, from: Date = new Date()): string[] {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth() - i, 1));
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    out.push(`${y}-${m}`);
  }
  return out;
}
