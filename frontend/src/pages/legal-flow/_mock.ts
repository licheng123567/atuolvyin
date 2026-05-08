// 法务转化订单 — 前端 mock 共享数据（PoC 阶段，三个工作台共用）
// 真实接入后端后整文件删除，改用 Refine useList/useOne。

export type OrderStatus = "pending" | "dispatched" | "in_service" | "completed" | "cancelled";
export type ServicePackage = "lawyer_letter" | "mediation" | "small_claims" | "full_agency";
export type DocType = "lawyer_letter" | "mediation_record" | "court_filing" | "judgment" | "other";

export interface LegalDoc {
  id: number;
  doc_type: DocType;
  doc_label: string;
  filename: string;
  uploaded_by: string;
  uploaded_at: string;
  url: string;
}

export interface LegalOrder {
  id: number;
  case_id: number;
  case_owner: string;
  case_building: string;
  case_amount: number;
  case_months_overdue: number;
  tenant_name: string;
  package: ServicePackage;
  package_label: string;
  status: OrderStatus;
  price_quoted: number;
  platform_fee_amount: number;
  law_firm_id: number | null;
  law_firm_name: string | null;
  lawyer_id: number | null;
  lawyer_name: string | null;
  created_by: string;
  created_at: string;
  dispatched_at: string | null;
  in_service_at: string | null;
  completed_at: string | null;
  notes: string | null;
  docs: LegalDoc[];
  timeline_summary: string;
}

export const PACKAGE_LABELS: Record<ServicePackage, string> = {
  lawyer_letter: "律师函",
  mediation: "诉前调解",
  small_claims: "小额诉讼",
  full_agency: "完整代理",
};

export const STATUS_LABELS: Record<OrderStatus, string> = {
  pending: "待撮合",
  dispatched: "已派单",
  in_service: "服务中",
  completed: "已完成",
  cancelled: "已取消",
};

export const STATUS_BADGES: Record<OrderStatus, string> = {
  pending: "ds-badge ds-badge-gray",
  dispatched: "ds-badge ds-badge-blue",
  in_service: "ds-badge ds-badge-orange",
  completed: "ds-badge ds-badge-green",
  cancelled: "ds-badge ds-badge-red",
};

export const DOC_LABELS: Record<DocType, string> = {
  lawyer_letter: "律师函",
  mediation_record: "调解记录",
  court_filing: "立案材料",
  judgment: "判决书",
  other: "其他文书",
};

// mock：当前登录律所 / 律师身份（实际由 token 解出）
export const MOCK_CURRENT_LAW_FIRM = { id: 1, name: "京诚律师事务所" };
export const MOCK_CURRENT_LAWYER = { id: 11, name: "李律师", law_firm_id: 1 };

export interface LawyerLite { id: number; name: string; law_firm_id: number; specialties: string[] }
export const MOCK_LAWYERS: LawyerLite[] = [
  { id: 11, name: "李律师", law_firm_id: 1, specialties: ["物业纠纷", "调解"] },
  { id: 12, name: "陈律师", law_firm_id: 1, specialties: ["小额诉讼"] },
  { id: 13, name: "周律师", law_firm_id: 1, specialties: ["律师函", "催收"] },
  { id: 21, name: "孙律师", law_firm_id: 2, specialties: ["大额诉讼"] },
];

const NOW = "2026-05-08";

const ORDERS: LegalOrder[] = [
  {
    id: 5001, case_id: 101, case_owner: "张大伟", case_building: "3-1201",
    case_amount: 24800, case_months_overdue: 18, tenant_name: "宏远物业",
    package: "full_agency", package_label: "完整代理", status: "in_service",
    price_quoted: 4800, platform_fee_amount: 1200,
    law_firm_id: 1, law_firm_name: "京诚律师事务所",
    lawyer_id: 11, lawyer_name: "李律师",
    created_by: "督导小李（宏远物业）", created_at: "2026-05-03 14:28",
    dispatched_at: "2026-05-04 09:12", in_service_at: "2026-05-04 15:30", completed_at: null,
    notes: "业主多次拒接，恶意拖欠倾向，建议直接立案",
    timeline_summary: "6 通通话，全部拒缴；触发 1 次 L1 风控",
    docs: [
      { id: 1, doc_type: "lawyer_letter", doc_label: "律师函", filename: "张大伟_律师函_20260504.pdf", uploaded_by: "李律师", uploaded_at: "2026-05-04 16:20", url: "#mock" },
    ],
  },
  {
    id: 5002, case_id: 102, case_owner: "王秀英", case_building: "8-0902",
    case_amount: 12600, case_months_overdue: 11, tenant_name: "宏远物业",
    package: "mediation", package_label: "诉前调解", status: "dispatched",
    price_quoted: 1800, platform_fee_amount: 450,
    law_firm_id: 1, law_firm_name: "京诚律师事务所",
    lawyer_id: null, lawyer_name: null,
    created_by: "督导小李（宏远物业）", created_at: "2026-05-06 11:30",
    dispatched_at: "2026-05-07 10:00", in_service_at: null, completed_at: null,
    notes: "业主反映服务质量问题，要求减免 50%，建议先调解",
    timeline_summary: "1 通通话，业主主张服务质量异议",
    docs: [],
  },
  {
    id: 5003, case_id: 103, case_owner: "刘建国", case_building: "1-0301",
    case_amount: 8400, case_months_overdue: 8, tenant_name: "宏远物业",
    package: "lawyer_letter", package_label: "律师函", status: "pending",
    price_quoted: 800, platform_fee_amount: 200,
    law_firm_id: null, law_firm_name: null,
    lawyer_id: null, lawyer_name: null,
    created_by: "督导小李（宏远物业）", created_at: "2026-05-07 16:42",
    dispatched_at: null, in_service_at: null, completed_at: null,
    notes: "业主已搬离 6 个月，新住户拒绝代缴",
    timeline_summary: "新住户回应：原业主已搬走",
    docs: [],
  },
  {
    id: 5004, case_id: 200, case_owner: "钱玉芳", case_building: "5-1102",
    case_amount: 18900, case_months_overdue: 15, tenant_name: "宏远物业",
    package: "small_claims", package_label: "小额诉讼", status: "completed",
    price_quoted: 3200, platform_fee_amount: 800,
    law_firm_id: 1, law_firm_name: "京诚律师事务所",
    lawyer_id: 12, lawyer_name: "陈律师",
    created_by: "督导小李（宏远物业）", created_at: "2026-04-15 09:20",
    dispatched_at: "2026-04-16 10:00", in_service_at: "2026-04-17 14:00", completed_at: "2026-05-02 16:30",
    notes: "已立案，业主一周内主动缴清，撤诉",
    timeline_summary: "立案后业主主动缴费 ¥18,900 + 违约金 ¥620",
    docs: [
      { id: 11, doc_type: "court_filing", doc_label: "立案材料", filename: "钱玉芳_立案_20260420.pdf", uploaded_by: "陈律师", uploaded_at: "2026-04-20 10:00", url: "#mock" },
      { id: 12, doc_type: "judgment", doc_label: "结案证明", filename: "钱玉芳_撤诉_20260502.pdf", uploaded_by: "陈律师", uploaded_at: "2026-05-02 16:30", url: "#mock" },
    ],
  },
  {
    id: 5005, case_id: 201, case_owner: "吴大山", case_building: "2-0408",
    case_amount: 6200, case_months_overdue: 5, tenant_name: "翠湖物业",
    package: "lawyer_letter", package_label: "律师函", status: "pending",
    price_quoted: 800, platform_fee_amount: 200,
    law_firm_id: null, law_firm_name: null,
    lawyer_id: null, lawyer_name: null,
    created_by: "督导张敏（翠湖物业）", created_at: "2026-05-08 08:15",
    dispatched_at: null, in_service_at: null, completed_at: null,
    notes: null,
    timeline_summary: "3 通失联",
    docs: [],
  },
];

// 单例 store（mock）
let _store: LegalOrder[] = ORDERS;
const _listeners: Set<() => void> = new Set();

export function getAllOrders(): LegalOrder[] {
  return _store;
}

export function getOrderById(id: number): LegalOrder | undefined {
  return _store.find((o) => o.id === id);
}

export function dispatchToFirm(orderId: number, lawFirmId: number, lawFirmName: string): void {
  _store = _store.map((o) =>
    o.id === orderId
      ? { ...o, law_firm_id: lawFirmId, law_firm_name: lawFirmName, status: "dispatched" as OrderStatus, dispatched_at: new Date().toISOString().slice(0, 19).replace("T", " ") }
      : o,
  );
  _listeners.forEach((fn) => fn());
}

export function assignLawyer(orderId: number, lawyerId: number, lawyerName: string): void {
  _store = _store.map((o) =>
    o.id === orderId
      ? { ...o, lawyer_id: lawyerId, lawyer_name: lawyerName, status: "in_service" as OrderStatus, in_service_at: new Date().toISOString().slice(0, 19).replace("T", " ") }
      : o,
  );
  _listeners.forEach((fn) => fn());
}

export function uploadDoc(orderId: number, doc: Omit<LegalDoc, "id">): void {
  _store = _store.map((o) =>
    o.id === orderId
      ? { ...o, docs: [...o.docs, { ...doc, id: Date.now() }] }
      : o,
  );
  _listeners.forEach((fn) => fn());
}

export function completeOrder(orderId: number): void {
  _store = _store.map((o) =>
    o.id === orderId
      ? { ...o, status: "completed" as OrderStatus, completed_at: new Date().toISOString().slice(0, 19).replace("T", " ") }
      : o,
  );
  _listeners.forEach((fn) => fn());
}

export function subscribe(fn: () => void): () => void {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}

export const TODAY = NOW;
