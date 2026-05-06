// frontend/src/pages/ops/providers/helpers.ts
//
// Pure helpers for service-provider list & detail pages. Side-effect free
// so they can be unit tested without React context.

export type AuditStatus = "pending" | "approved" | "rejected";
export type ProviderType = "legal" | "collection" | "both";

export const AUDIT_STATUS_LABELS: Record<AuditStatus, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};

export const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  legal: "法务",
  collection: "催收",
  both: "法务+催收",
};

/**
 * Tailwind class for an audit-status badge.
 * pending=yellow, approved=green, rejected=red. Unknown → gray.
 */
export function getAuditStatusColor(status: string): string {
  switch (status) {
    case "pending":
      return "bg-yellow-100 text-yellow-700";
    case "approved":
      return "bg-green-100 text-green-700";
    case "rejected":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

/** Localised label for an audit-status value; passthrough for unknown. */
export function formatAuditStatus(status: string): string {
  return AUDIT_STATUS_LABELS[status as AuditStatus] ?? status;
}

/** Localised label for a provider type; passthrough for unknown. */
export function formatProviderType(t: string): string {
  return PROVIDER_TYPE_LABELS[t as ProviderType] ?? t;
}

/**
 * Days remaining until an ISO date string, ceil-style. Returns null when
 * input is empty/invalid. Negative deltas clamp to 0 (already expired).
 */
export function daysUntil(
  isoDate: string | null | undefined,
  now: Date = new Date(),
): number | null {
  if (!isoDate) return null;
  const t = new Date(isoDate).getTime();
  if (Number.isNaN(t)) return null;
  const diffMs = t - now.getTime();
  if (diffMs <= 0) return 0;
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Tailwind class for a trial-row urgency badge:
 * <=3 days → red, <=7 days → yellow, otherwise → neutral.
 * `null` (no expiry) returns the neutral style.
 */
export function getTrialUrgencyColor(days: number | null): string {
  if (days === null) return "bg-gray-100 text-gray-600";
  if (days <= 3) return "bg-red-100 text-red-700";
  if (days <= 7) return "bg-yellow-100 text-yellow-700";
  return "bg-gray-100 text-gray-700";
}
