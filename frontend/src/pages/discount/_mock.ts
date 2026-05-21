// 协商打折 / 减免回款 — 前端 mock 共享数据（PoC）
// v1.6 接后端 settlement_offer 表 + 审批工作流

export type OfferType =
  | "principal_discount"      // 本金减免（直接打折）
  | "late_fee_waive"          // 违约金减免
  | "installment"             // 分期还款
  | "long_overdue_compromise"; // 长账龄一次性结清折扣

export type OfferStatus =
  | "pending_supervisor"  // 待督导审批
  | "pending_admin"       // 待物业 admin 审批
  | "approved"            // 审批通过
  | "rejected"            // 拒绝
  | "executed"            // 业主已按方案缴清
  | "expired";            // 业主未在 offer 有效期内执行

export interface DiscountOffer {
  id: number;
  case_id: number;
  case_owner: string;
  case_building: string;
  project_name: string;
  tenant_name: string;
  applicant_name: string;          // 催收员名
  applicant_role: "agent" | "supervisor";
  offer_type: OfferType;
  offer_type_label: string;
  original_amount: number;          // 原欠费
  proposed_amount: number;          // 业主同意支付的金额
  discount_pct: number;             // = (original - proposed) / original × 100
  installment_months: number | null; // 分期月数（offer_type === installment 时填）
  reason: string;                   // 申请理由（业主原话 + 催收员判断）
  status: OfferStatus;
  approver_role_required: "supervisor" | "admin"; // 按 discount_pct 自动判定
  current_approver_name: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejected_reason: string | null;
  expires_at: string;               // 业主必须在此日期前缴清
  created_at: string;
  audit_trail: { time: string; actor: string; action: string }[];
}

export const OFFER_TYPE_LABELS: Record<OfferType, string> = {
  principal_discount: "本金减免",
  late_fee_waive: "违约金减免",
  installment: "分期还款",
  long_overdue_compromise: "长账龄一次结清",
};

export const STATUS_LABELS: Record<OfferStatus, string> = {
  pending_supervisor: "待督导审批",
  pending_admin: "待物业管理员审批",
  approved: "已批准",
  rejected: "已拒绝",
  executed: "已执行",
  expired: "已过期",
};

export const STATUS_BADGES: Record<OfferStatus, string> = {
  pending_supervisor: "ds-badge ds-badge-orange",
  pending_admin: "ds-badge ds-badge-orange",
  approved: "ds-badge ds-badge-blue",
  rejected: "ds-badge ds-badge-red",
  executed: "ds-badge ds-badge-green",
  expired: "ds-badge ds-badge-gray",
};

// 权限矩阵：按减免比例决定审批人
// v1.6 — 阈值改为 admin 在 TenantSettings 配置；保留默认值用于兜底
const DEFAULT_AUTO_THRESHOLD = 10;
const DEFAULT_SUPERVISOR_MAX = 30;
export function decideApproverRole(
  discountPct: number,
  policy: { autoThreshold?: number; supervisorMax?: number } = {},
): "auto" | "supervisor" | "admin" {
  const auto = policy.autoThreshold ?? DEFAULT_AUTO_THRESHOLD;
  const sup = policy.supervisorMax ?? DEFAULT_SUPERVISOR_MAX;
  if (discountPct < auto) return "auto";
  if (discountPct <= sup) return "supervisor";
  return "admin";
}

const MOCK_OFFERS: DiscountOffer[] = [
  {
    id: 7001, case_id: 101, case_owner: "张大伟", case_building: "3-1201",
    project_name: "金桂园 2026 年欠费催收", tenant_name: "宏远物业",
    applicant_name: "李小红", applicant_role: "agent",
    offer_type: "principal_discount", offer_type_label: "本金减免",
    original_amount: 24800, proposed_amount: 19840, discount_pct: 20,
    installment_months: null,
    reason: "业主表示家庭遭遇变故（配偶失业 6 个月），愿一次性缴 ¥19,840，需要减免 20%。",
    status: "pending_supervisor",
    approver_role_required: "supervisor",
    current_approver_name: "督导小李",
    approved_by: null, approved_at: null, rejected_reason: null,
    expires_at: "2026-05-15",
    created_at: "2026-05-08 14:20",
    audit_trail: [
      { time: "2026-05-08 14:20", actor: "李小红", action: "发起减免申请" },
    ],
  },
  {
    id: 7002, case_id: 102, case_owner: "王秀英", case_building: "8-0902",
    project_name: "金桂园 2026 年欠费催收", tenant_name: "宏远物业",
    applicant_name: "王芳芳", applicant_role: "agent",
    offer_type: "principal_discount", offer_type_label: "本金减免",
    original_amount: 12600, proposed_amount: 6300, discount_pct: 50,
    installment_months: null,
    reason: "业主主张电梯故障 3 次的服务质量问题，要求减免 50%。需物业管理员审批。",
    status: "pending_admin",
    approver_role_required: "admin",
    current_approver_name: "物业管理员",
    approved_by: null, approved_at: null, rejected_reason: null,
    expires_at: "2026-05-15",
    created_at: "2026-05-07 11:35",
    audit_trail: [
      { time: "2026-05-07 11:35", actor: "王芳芳", action: "发起减免申请（50%）" },
      { time: "2026-05-07 16:00", actor: "督导小李", action: "转交物业管理员审批（金额超督导权限）" },
    ],
  },
  {
    id: 7003, case_id: 103, case_owner: "刘建国", case_building: "1-0301",
    project_name: "翠湖湾电梯专项整改", tenant_name: "宏远物业",
    applicant_name: "张建华", applicant_role: "agent",
    offer_type: "installment", offer_type_label: "分期还款",
    original_amount: 8400, proposed_amount: 8400, discount_pct: 0,
    installment_months: 6,
    reason: "业主收入不稳定但愿意还款，申请 6 期分期。无折扣。",
    status: "approved",
    approver_role_required: "supervisor",
    current_approver_name: null,
    approved_by: "督导小李", approved_at: "2026-05-04 10:30",
    rejected_reason: null,
    expires_at: "2026-11-04",
    created_at: "2026-05-04 09:15",
    audit_trail: [
      { time: "2026-05-04 09:15", actor: "张建华", action: "发起分期申请（6 期）" },
      { time: "2026-05-04 10:30", actor: "督导小李", action: "批准 — 6 期分期，每期 ¥1,400" },
    ],
  },
  {
    id: 7004, case_id: 200, case_owner: "钱玉芳", case_building: "5-1102",
    project_name: "金桂园 2026 年欠费催收", tenant_name: "宏远物业",
    applicant_name: "陈明远", applicant_role: "agent",
    offer_type: "late_fee_waive", offer_type_label: "违约金减免",
    original_amount: 1800, proposed_amount: 0, discount_pct: 100,
    installment_months: null,
    reason: "业主一周内主动缴清欠费 ¥18,900，申请减免违约金 ¥1,800。",
    status: "executed",
    approver_role_required: "supervisor",
    current_approver_name: null,
    approved_by: "督导小李", approved_at: "2026-05-02 17:00",
    rejected_reason: null,
    expires_at: "2026-05-09",
    created_at: "2026-05-02 16:30",
    audit_trail: [
      { time: "2026-05-02 16:30", actor: "陈明远", action: "发起违约金减免申请" },
      { time: "2026-05-02 17:00", actor: "督导小李", action: "批准（业主已缴清本金）" },
      { time: "2026-05-02 18:30", actor: "系统", action: "业主已按方案执行 — offer 完成" },
    ],
  },
];

let _store: DiscountOffer[] = MOCK_OFFERS;
const _listeners = new Set<() => void>();

export function getAllOffers(): DiscountOffer[] {
  return _store;
}

export function getOffersForApprover(role: "supervisor" | "admin"): DiscountOffer[] {
  if (role === "supervisor") return _store.filter((o) => o.status === "pending_supervisor");
  return _store.filter((o) => o.status === "pending_admin");
}

export function getOfferById(id: number): DiscountOffer | undefined {
  return _store.find((o) => o.id === id);
}

export function approveOffer(id: number, approverName: string, note: string): void {
  _store = _store.map((o) => {
    if (o.id !== id) return o;
    return {
      ...o,
      status: "approved",
      approved_by: approverName,
      approved_at: new Date().toISOString().slice(0, 19).replace("T", " "),
      audit_trail: [
        ...o.audit_trail,
        { time: new Date().toISOString().slice(0, 19).replace("T", " "), actor: approverName, action: `批准${note ? "（" + note + "）" : ""}` },
      ],
    };
  });
  _listeners.forEach((fn) => fn());
}

export function rejectOffer(id: number, approverName: string, reason: string): void {
  _store = _store.map((o) => {
    if (o.id !== id) return o;
    return {
      ...o,
      status: "rejected",
      rejected_reason: reason,
      approved_at: new Date().toISOString().slice(0, 19).replace("T", " "),
      audit_trail: [
        ...o.audit_trail,
        { time: new Date().toISOString().slice(0, 19).replace("T", " "), actor: approverName, action: `拒绝 — ${reason}` },
      ],
    };
  });
  _listeners.forEach((fn) => fn());
}

export function escalateToAdmin(id: number, supervisorName: string, note: string): void {
  _store = _store.map((o) => {
    if (o.id !== id) return o;
    return {
      ...o,
      status: "pending_admin",
      approver_role_required: "admin",
      current_approver_name: "物业管理员",
      audit_trail: [
        ...o.audit_trail,
        { time: new Date().toISOString().slice(0, 19).replace("T", " "), actor: supervisorName, action: `转交物业管理员审批${note ? "（" + note + "）" : ""}` },
      ],
    };
  });
  _listeners.forEach((fn) => fn());
}

export function createOffer(input: {
  case_id: number;
  case_owner: string;
  case_building: string;
  project_name: string;
  tenant_name: string;
  applicant_name: string;
  applicant_role: "agent" | "supervisor";
  offer_type: OfferType;
  original_amount: number;
  proposed_amount: number;
  installment_months: number | null;
  reason: string;
}): DiscountOffer {
  const discount_pct = input.original_amount > 0
    ? Math.round(((input.original_amount - input.proposed_amount) / input.original_amount) * 100)
    : 0;
  const decision = decideApproverRole(discount_pct);
  let status: OfferStatus;
  let approver_role_required: "supervisor" | "admin";
  let current_approver_name: string | null;
  if (decision === "auto") {
    status = "approved";
    approver_role_required = "supervisor";
    current_approver_name = null;
  } else if (decision === "supervisor") {
    status = "pending_supervisor";
    approver_role_required = "supervisor";
    current_approver_name = "督导小李";
  } else {
    status = "pending_admin";
    approver_role_required = "admin";
    current_approver_name = "物业管理员";
  }
  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  const expiresAt = new Date(Date.now() + 7 * 86400_000).toISOString().slice(0, 10);
  const offer: DiscountOffer = {
    id: 7000 + _store.length + 1,
    case_id: input.case_id,
    case_owner: input.case_owner,
    case_building: input.case_building,
    project_name: input.project_name,
    tenant_name: input.tenant_name,
    applicant_name: input.applicant_name,
    applicant_role: input.applicant_role,
    offer_type: input.offer_type,
    offer_type_label: OFFER_TYPE_LABELS[input.offer_type],
    original_amount: input.original_amount,
    proposed_amount: input.proposed_amount,
    discount_pct,
    installment_months: input.installment_months,
    reason: input.reason,
    status,
    approver_role_required,
    current_approver_name,
    approved_by: decision === "auto" ? "系统自动（<10%）" : null,
    approved_at: decision === "auto" ? now : null,
    rejected_reason: null,
    expires_at: expiresAt,
    created_at: now,
    audit_trail: [
      { time: now, actor: input.applicant_name, action: `发起${OFFER_TYPE_LABELS[input.offer_type]}申请（${discount_pct}%）` },
      ...(decision === "auto" ? [{ time: now, actor: "系统", action: "自动批准（折扣 < 10%）" }] : []),
    ],
  };
  _store = [..._store, offer];
  _listeners.forEach((fn) => fn());
  return offer;
}

export function subscribe(fn: () => void): () => void {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}
