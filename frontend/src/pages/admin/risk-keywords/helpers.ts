// Helpers extracted from list.tsx so that the page file exports only React
// components (Fast Refresh requirement: react-refresh/only-export-components).

export interface RiskKeywordItem {
  id: number;
  tenant_id: number | null;
  category: string;
  speaker: string;
  level: string;
  keyword: string;
  is_active: boolean;
  created_at: string;
}

export function isPlatformPreset(item: Pick<RiskKeywordItem, "tenant_id">): boolean {
  return item.tenant_id === null;
}
