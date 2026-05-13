// v2.0 Task 4 — Case stage label / badge mapping
// 移动端复用（Screen 1 home / Screen 5 cases / Screen 6 detail）。
// PC 端有自己的映射（不复用此处，颜色 token 不同）。

export const STAGE_LABEL: Record<string, string> = {
  new: "待跟进",
  in_progress: "跟进中",
  promised: "承诺缴费",
  paid: "已缴费",
  escalated: "升级",
  closed: "已关闭",
};

// 设计稿用的轻量 badge（design-system.css 里的 .badge.badge-{color}）
export const STAGE_BADGE: Record<string, string> = {
  new: "badge badge-orange",
  in_progress: "badge badge-orange",
  promised: "badge badge-green",
  paid: "badge badge-blue",
  escalated: "badge badge-red",
  closed: "badge badge-gray",
};

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return "—";
  return STAGE_LABEL[stage] ?? stage;
}

export function stageBadgeClass(stage: string | null | undefined): string {
  if (!stage) return "badge badge-gray";
  return STAGE_BADGE[stage] ?? "badge badge-gray";
}

// 通话 result_tag → badge（参考 PC 版 RESULT_OPTIONS）
export interface ResultBadge {
  label: string;
  cls: string;
}

export function resultTagBadge(tag: string | null | undefined): ResultBadge {
  if (!tag) return { label: "—", cls: "badge badge-gray" };
  if (tag.includes("paid")) return { label: "已回款", cls: "badge badge-blue" };
  if (tag.includes("promised")) return { label: "承诺缴费", cls: "badge badge-green" };
  if (tag.includes("refused")) return { label: "拒绝缴费", cls: "badge badge-red" };
  if (tag.includes("missed")) return { label: "未接通", cls: "badge badge-gray" };
  if (tag.includes("followup")) return { label: "需跟进", cls: "badge badge-gray" };
  return { label: tag, cls: "badge badge-gray" };
}
