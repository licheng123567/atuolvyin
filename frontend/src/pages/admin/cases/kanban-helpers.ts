// frontend/src/pages/admin/cases/kanban-helpers.ts

export const STAGES = [
  "new",
  "in_progress",
  "promised",
  "paid",
  "escalated",
  "closed",
] as const;

export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  new: "待联系",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级中",
  closed: "已关闭",
};

/** Left-border colors matching the UI prototype (admin.html) */
export const STAGE_BORDER_COLORS: Record<Stage, string> = {
  new: "#9ca3af",
  in_progress: "#1A56DB",
  promised: "#d97706",
  paid: "#057a55",
  escalated: "#7e3af2",
  closed: "#9ca3af",
};

/** Column header background + text + count-badge colors (admin.html col-* classes) */
export const STAGE_HEADER_COLORS: Record<
  Stage,
  { headerBg: string; headerText: string; badgeBg: string; badgeText: string }
> = {
  new: {
    headerBg: "#f3f4f6",
    headerText: "#374151",
    badgeBg: "#e5e7eb",
    badgeText: "#374151",
  },
  in_progress: {
    headerBg: "#eff6ff",
    headerText: "#1d4ed8",
    badgeBg: "#dbeafe",
    badgeText: "#1d4ed8",
  },
  promised: {
    headerBg: "#fffbeb",
    headerText: "#b45309",
    badgeBg: "#fde68a",
    badgeText: "#b45309",
  },
  paid: {
    headerBg: "#f0fdf4",
    headerText: "#065f46",
    badgeBg: "#bbf7d0",
    badgeText: "#065f46",
  },
  escalated: {
    headerBg: "#f5f3ff",
    headerText: "#6d28d9",
    badgeBg: "#ddd6fe",
    badgeText: "#6d28d9",
  },
  closed: {
    headerBg: "#f3f4f6",
    headerText: "#6b7280",
    badgeBg: "#e5e7eb",
    badgeText: "#6b7280",
  },
};

export function groupByStage<T extends { stage: string }>(
  cases: T[],
): Record<Stage, T[]> {
  const groups: Record<Stage, T[]> = {
    new: [],
    in_progress: [],
    promised: [],
    paid: [],
    escalated: [],
    closed: [],
  };
  for (const c of cases) {
    if (c.stage in groups) {
      groups[c.stage as Stage].push(c);
    }
    // unknown stage values are silently ignored (no crash)
  }
  return groups;
}
