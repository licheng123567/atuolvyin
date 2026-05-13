// v1.6.6 — 案件相关共享常量（admin/agent 详情页 / 工作台 共用）

export const STAGE_LABELS: Record<string, string> = {
  new: "待联系",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级中",
  closed: "已关闭",
};

export const STAGE_BADGE_CLASS: Record<string, string> = {
  new: "ds-badge ds-badge-gray",
  in_progress: "ds-badge ds-badge-blue",
  promised: "ds-badge ds-badge-orange",
  paid: "ds-badge ds-badge-green",
  escalated: "ds-badge ds-badge-purple",
  closed: "ds-badge ds-badge-gray",
};

export const RESULT_TAG_BADGE_CLASS: Record<string, string> = {
  承诺缴: "ds-badge ds-badge-orange",
  立即缴: "ds-badge ds-badge-green",
  推托: "ds-badge ds-badge-orange",
  拒缴: "ds-badge ds-badge-red",
};

export const CHARGE_PERIOD_LABELS: Record<string, string> = {
  monthly: "按月",
  quarterly: "按季",
  semiannual: "按半年",
  annual: "按年",
};

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  preliminary_service: "前期物业服务合同",
  elected: "选聘合同",
  re_elected: "续聘合同",
  interim_management: "临时管理合同",
};

export function legalStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  switch (status) {
    case "pending": return "待撮合";
    case "dispatched": return "已派单";
    case "in_service": return "服务中";
    case "completed": return "已完结";
    default: return status;
  }
}

export function formatDuration(sec: number | null | undefined): string {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}分${s}秒`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
