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
