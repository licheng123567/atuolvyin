// frontend/src/pages/supervisor/helpers.ts
export type LabelStatus = "unlabeled" | "good" | "bad";

export function getLabelStatus(label: string | null): LabelStatus {
  if (!label) return "unlabeled";
  if (label === "good") return "good";
  return "bad";
}
