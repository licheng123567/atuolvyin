// Helpers extracted from detail.tsx so the page exports only React components
// (Fast Refresh requirement: react-refresh/only-export-components).

export interface RiskEntry {
  risk_id: string;
  level: string;
  category: string;
  trigger: string;
  text_snippet: string;
  matched_keywords: string[];
  llm_confidence: number;
  speaker: string;
}

export interface RiskAnnotation {
  risk_id: string;
  level: string;
  category: string;
  trigger: string;
  matched_keywords: string[];
  llm_confidence: number;
}

export function getRiskAnnotationForSegment(
  segmentText: string,
  risks: RiskEntry[],
): RiskAnnotation | null {
  for (const risk of risks) {
    if (risk.text_snippet && segmentText.includes(risk.text_snippet)) {
      return {
        risk_id: risk.risk_id,
        level: risk.level,
        category: risk.category,
        trigger: risk.trigger,
        matched_keywords: risk.matched_keywords,
        llm_confidence: risk.llm_confidence,
      };
    }
  }
  return null;
}
