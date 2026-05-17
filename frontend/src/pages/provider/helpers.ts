// frontend/src/pages/provider/helpers.ts
//
// Pure helpers shared across the provider-side admin pages
// (admin role with scope=provider:{id}: dashboard / tenants / team / settlements).
// Side-effect-free so they can be unit-tested without React context.

export type ContractStatus = "active" | "expired" | "terminated" | string;

/**
 * Format a numeric/string amount as a "¥X.XX" currency string with thousand
 * separators. Falls back to "¥0.00" for null/undefined/NaN inputs.
 *
 * Used for the dashboard 本月收入 / 待结算金额 KPI cards and any other
 * money cell on the provider workstation pages.
 */
export function formatRevenue(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return "¥0.00";
  const num = typeof n === "string" ? Number(n) : n;
  if (!Number.isFinite(num)) return "¥0.00";
  return `¥${num.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Tailwind class for a contract status pill. active=green, expired=gray,
 * terminated=red. Anything else falls back to neutral gray.
 */
export function getContractStatusColor(status: string): string {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-700";
    case "expired":
      return "bg-gray-100 text-gray-600";
    case "terminated":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

const CONTRACT_STATUS_LABELS: Record<string, string> = {
  active: "履约中",
  expired: "已到期",
  terminated: "已终止",
};

export function getContractStatusLabel(status: string): string {
  return CONTRACT_STATUS_LABELS[status] ?? status;
}

/**
 * Format an ISO datetime as YYYY-MM-DD. Returns "—" on invalid/empty input.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Returns the last `n` year-month options (newest first). Mirrors the
 * helper used by /admin/settlements; duplicated here to avoid coupling
 * the provider page to admin internals.
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
