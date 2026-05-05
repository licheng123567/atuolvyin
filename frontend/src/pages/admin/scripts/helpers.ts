// frontend/src/pages/admin/scripts/helpers.ts
export function getScoreGradeColor(grade: string | null): string {
  switch (grade) {
    case "A": return "text-green-700 bg-green-50 border-green-200";
    case "B": return "text-blue-700 bg-blue-50 border-blue-200";
    case "C": return "text-orange-700 bg-orange-50 border-orange-200";
    case "D": return "text-red-700 bg-red-50 border-red-200";
    default:  return "text-gray-500 bg-gray-50 border-gray-200";
  }
}

export function formatAdoptionRate(rate: number | null): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export const TRIGGER_INTENTS = [
  "房屋质量",
  "经济困难",
  "服务不满",
  "联系困难",
  "其他",
] as const;

export type TriggerIntent = typeof TRIGGER_INTENTS[number];
