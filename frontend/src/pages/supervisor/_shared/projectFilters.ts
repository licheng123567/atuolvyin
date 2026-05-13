// 督导端共享：项目过滤选项常量（与各 mock 数据保持一致）
export const SUPERVISOR_PROJECT_FILTERS = [
  "全部项目",
  "金桂园 2026 年欠费催收",
  "翠湖湾电梯专项整改",
] as const;

export type SupervisorProjectFilter = (typeof SUPERVISOR_PROJECT_FILTERS)[number];
