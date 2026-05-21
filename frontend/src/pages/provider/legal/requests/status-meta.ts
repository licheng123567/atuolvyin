// §9 — 审批状态 Badge 共享常量（[id].tsx 与 index.tsx 共用）
export interface StatusMeta {
  label: string;
  background: string;
  color: string;
}

export const STATUS_META: Record<string, StatusMeta> = {
  pending:   { label: "待审批", background: "#FEF3C7", color: "#D97706" },
  approved:  { label: "已通过", background: "#DCFCE7", color: "#057A55" },
  rejected:  { label: "已驳回", background: "#FEE2E2", color: "#E02424" },
  cancelled: { label: "已取消", background: "#F3F4F6", color: "#4B5563" },
};

export const UNKNOWN_STATUS_META: StatusMeta = { label: "未知", background: "#F3F4F6", color: "#4B5563" };
