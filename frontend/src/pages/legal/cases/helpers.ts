// Shared helpers for the legal/cases pages.

export const LEGAL_STAGES = [
  "pending_eval",
  "evidence_collection",
  "litigation_filed",
  "judgment_pending",
  "enforcing",
  "closed_won",
  "closed_lost",
  "closed_settled",
] as const;

export type LegalStage = (typeof LEGAL_STAGES)[number];

export const LEGAL_STAGE_LABELS: Record<LegalStage, string> = {
  pending_eval: "待评估",
  evidence_collection: "取证中",
  litigation_filed: "已立案",
  judgment_pending: "待判决",
  enforcing: "执行中",
  closed_won: "胜诉结案",
  closed_lost: "败诉结案",
  closed_settled: "和解结案",
};

export function formatStage(stage: string): string {
  return LEGAL_STAGE_LABELS[stage as LegalStage] ?? stage;
}

export function getStageColor(stage: string): React.CSSProperties {
  switch (stage) {
    case "pending_eval":
      return {
        background: "var(--color-neutral-100)",
        color: "var(--color-neutral-600)",
      };
    case "evidence_collection":
      return {
        background: "var(--color-warning-light)",
        color: "var(--color-warning)",
      };
    case "litigation_filed":
    case "judgment_pending":
      return {
        background: "var(--color-primary-light)",
        color: "var(--color-primary)",
      };
    case "enforcing":
      return {
        background: "var(--color-warning-light)",
        color: "var(--color-warning)",
      };
    case "closed_won":
    case "closed_settled":
      return {
        background: "var(--color-success-light)",
        color: "var(--color-success)",
      };
    case "closed_lost":
      return {
        background: "var(--color-danger-light)",
        color: "var(--color-danger)",
      };
    default:
      return {
        background: "var(--color-neutral-100)",
        color: "var(--color-neutral-600)",
      };
  }
}

export function isClosedStage(stage: string): boolean {
  return (
    stage === "closed_won" ||
    stage === "closed_lost" ||
    stage === "closed_settled"
  );
}
