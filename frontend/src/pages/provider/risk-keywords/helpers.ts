// v1.0.0 — 服务商风控关键词 helpers(对齐物业 admin)。

export interface RiskKeywordItem {
  id: number;
  tenant_id: number | null;
  provider_id: number | null;
  category: string;
  speaker: string;
  level: string;
  keyword: string;
  is_active: boolean;
  created_at: string;
}

/** 平台预置:tenant_id 和 provider_id 都为 NULL */
export function isPlatformPreset(
  item: Pick<RiskKeywordItem, "tenant_id" | "provider_id">,
): boolean {
  return item.tenant_id === null && item.provider_id === null;
}
