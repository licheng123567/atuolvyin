// v1.6 — 减免策略 hooks
// v1.6.1 — 加项目级覆盖：按 caseId 查 effective policy
// v1.6.2 — 拆分本金打折 + 滞纳金减免两类
import { useCustom } from "@refinedev/core";

interface TenantSettingsDiscountFields {
  discount_auto_approve_threshold_pct: number;
  discount_supervisor_max_pct: number;
  discount_disabled: boolean;
  late_fee_waive_auto_approve_threshold_pct?: number;
  late_fee_waive_supervisor_max_pct?: number;
  late_fee_waive_disabled?: boolean;
}

interface PolicyBlock {
  auto_threshold: number;
  supervisor_max: number;
  disabled: boolean;
  source: "project" | "tenant";
}

interface CasePolicyResp {
  case_id: number;
  project_id: number | null;
  project_name: string | null;
  // 旧字段（= principal_discount，保留兼容）
  auto_threshold: number;
  supervisor_max: number;
  disabled: boolean;
  source: "project" | "tenant";
  // v1.6.2 — 拆分两类
  principal_discount?: PolicyBlock;
  late_fee_waive?: PolicyBlock;
}

export type OfferKind = "principal_discount" | "late_fee_waive" | "installment" | "long_overdue_compromise";

export interface DiscountPolicy {
  /** 折扣 < autoThreshold 时系统自动批准 */
  autoThreshold: number;
  /** 折扣 ≤ supervisorMax 时督导可批；> supervisorMax 转 admin */
  supervisorMax: number;
  /** true 表示完全禁用减免功能 */
  disabled: boolean;
  /** 加载中 */
  isLoading: boolean;
  /** 'project' = 来自项目级覆盖；'tenant' = 来自租户默认 */
  source?: "project" | "tenant";
  /** 项目名（若 source=project）*/
  projectName?: string | null;
}

const DEFAULT_POLICY: Omit<DiscountPolicy, "isLoading"> = {
  autoThreshold: 10,
  supervisorMax: 30,
  disabled: false,
};

/** 仅拉租户级策略（不区分项目）— supervisor/admin 减免审批页用。
 *  v2.2 — 改用 discount-policy 端点（supervisor 可读），不再调 admin/settings（admin 专属）。
 */
export function useDiscountPolicy(): DiscountPolicy {
  const { query } = useCustom<TenantSettingsDiscountFields>({
    url: "discount-policy",
    method: "get",
    queryOptions: { staleTime: 60_000, retry: false },
  });
  const data = query.data?.data;
  return {
    autoThreshold: data?.discount_auto_approve_threshold_pct ?? DEFAULT_POLICY.autoThreshold,
    supervisorMax: data?.discount_supervisor_max_pct ?? DEFAULT_POLICY.supervisorMax,
    disabled: data?.discount_disabled ?? DEFAULT_POLICY.disabled,
    isLoading: query.isLoading,
  };
}

/** v1.6.1 — 按 caseId 拉 effective policy（项目级覆盖后）。默认返回「本金打折」策略以兼容旧调用。 */
export function useDiscountPolicyForCase(
  caseId: number | null | undefined,
  kind: OfferKind = "principal_discount",
): DiscountPolicy {
  const { query } = useCustom<CasePolicyResp>({
    url: caseId ? `cases/${caseId}/discount-policy` : "cases/0/discount-policy",
    method: "get",
    queryOptions: { enabled: !!caseId, staleTime: 30_000, retry: false },
  });
  const data = query.data?.data;
  // v1.6.2 — 滞纳金减免单独走 late_fee_waive；其他类型走 principal_discount（旧字段）
  const block: PolicyBlock | undefined =
    kind === "late_fee_waive"
      ? data?.late_fee_waive
      : data?.principal_discount;
  // 若后端旧版本（无新字段），fallback 到顶层 auto_threshold/supervisor_max（即本金打折）
  const fallback = data
    ? { auto_threshold: data.auto_threshold, supervisor_max: data.supervisor_max, disabled: data.disabled, source: data.source }
    : undefined;
  const eff = block ?? fallback;
  return {
    autoThreshold: eff?.auto_threshold ?? DEFAULT_POLICY.autoThreshold,
    supervisorMax: eff?.supervisor_max ?? DEFAULT_POLICY.supervisorMax,
    disabled: eff?.disabled ?? DEFAULT_POLICY.disabled,
    isLoading: query.isLoading,
    source: eff?.source,
    projectName: data?.project_name,
  };
}

/** 按 policy 决定一个折扣比例的审批人。 */
export function decideApproverRoleWithPolicy(
  discountPct: number,
  policy: { autoThreshold: number; supervisorMax: number },
): "auto" | "supervisor" | "admin" {
  if (discountPct < policy.autoThreshold) return "auto";
  if (discountPct <= policy.supervisorMax) return "supervisor";
  return "admin";
}
