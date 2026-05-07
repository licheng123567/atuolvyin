// Shared helpers for workorder/orders pages.

export const WORK_ORDER_STATUSES = [
  "open",
  "in_progress",
  "resolved",
  "closed",
] as const;

export type WorkOrderStatus = (typeof WORK_ORDER_STATUSES)[number];

export const WORK_ORDER_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  open: "待处理",
  in_progress: "处理中",
  resolved: "已解决",
  closed: "已关闭",
};

export const WORK_ORDER_TYPES = [
  "quality",
  "reduction",
  "dispute",
  "other",
] as const;

export type WorkOrderType = (typeof WORK_ORDER_TYPES)[number];

export const WORK_ORDER_TYPE_LABELS: Record<WorkOrderType, string> = {
  quality: "服务质量",
  reduction: "减免申请",
  dispute: "费用争议",
  other: "其他",
};

export function formatStatus(status: string): string {
  return WORK_ORDER_STATUS_LABELS[status as WorkOrderStatus] ?? status;
}

export function formatType(t: string): string {
  return WORK_ORDER_TYPE_LABELS[t as WorkOrderType] ?? t;
}

export function getStatusColor(status: string): React.CSSProperties {
  switch (status) {
    case "open":
      return {
        background: "var(--color-warning-light)",
        color: "var(--color-warning)",
      };
    case "in_progress":
      return {
        background: "var(--color-primary-light)",
        color: "var(--color-primary)",
      };
    case "resolved":
      return {
        background: "var(--color-success-light)",
        color: "var(--color-success)",
      };
    case "closed":
      return {
        background: "var(--color-neutral-100)",
        color: "var(--color-neutral-600)",
      };
    default:
      return {
        background: "var(--color-neutral-100)",
        color: "var(--color-neutral-600)",
      };
  }
}

export function isTerminalStatus(status: string): boolean {
  return status === "resolved" || status === "closed";
}

// v1.6 — 4 档优先级（对齐 ui/workorder.html badge 风格）
export const WORK_ORDER_PRIORITIES = [
  "urgent_critical",
  "urgent",
  "normal",
  "low",
] as const;

export type WorkOrderPriority = (typeof WORK_ORDER_PRIORITIES)[number];

export const WORK_ORDER_PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  urgent_critical: "很紧急",
  urgent: "紧急",
  normal: "一般",
  low: "低",
};

export function formatPriority(priority: string): string {
  return (
    WORK_ORDER_PRIORITY_LABELS[priority as WorkOrderPriority] ?? priority
  );
}

export function getPriorityColor(priority: string): React.CSSProperties {
  switch (priority) {
    case "urgent_critical":
      return {
        background: "var(--color-danger-light)",
        color: "var(--color-danger)",
      };
    case "urgent":
      return {
        background: "var(--color-warning-light)",
        color: "var(--color-warning)",
      };
    case "normal":
    case "low":
    default:
      return {
        background: "var(--color-neutral-100)",
        color: "var(--color-neutral-600)",
      };
  }
}
