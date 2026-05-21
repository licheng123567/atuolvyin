export interface CaseCallItem {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  status: string;
  transcript_preview: string | null;
  result_tag: string | null;
  confidence: number | null;
  agent_name: string | null;
  recording_url?: string | null;  // v1.6.7 — E5 inline 录音
}

export interface TimelineEvent {
  type: string;
  ts: string;
  actor: string | null;
  note: string | null;
  // v1.6.9 — 关联实体 ID + 类型，让前端能跳到对应详情页
  target_id?: number | null;
  target_type?: "workorder" | "legal_order" | "legal_case" | "call" | "audit" | null;
}

export interface OwnerInfo {
  id: number;
  name: string;
  phone: string | null;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

export interface CaseProjectInfo {
  name: string;
  charge_rate_text: string | null;
  charge_period: string | null;
  contract_type: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  contract_attachment_key: string | null;
  contract_attachment_filename: string | null;
  charge_notes: string | null;
}

export interface CaseDetailResponse {
  id: number;
  tenant_id: number;
  project_id: number | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  // v1.0.0 — 案件详情显示催收员姓名(物业 + 服务商 admin 详情页都用)
  assigned_to_name?: string | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  // v1.6.3 — 账单字段（导入时录入，不再按月推算）
  bill_period_start?: string | null;
  bill_period_end?: string | null;
  principal_amount?: string | null;
  late_fee_amount?: string | null;
  arrears_reason?: string | null;
  priority_score: number;
  last_contact_at: string | null;
  monthly_contact_count: number;
  // v1.8.0 — 业主画像 3 统计卡片
  promise_count?: number;
  workorder_count?: number;
  status: string;
  created_at: string;
  updated_at: string;
  calls: CaseCallItem[];
  timeline_events: TimelineEvent[];
  project_name?: string | null;
  project_info?: CaseProjectInfo | null;  // v1.6.3
  assigned_role?: string | null;
  // v1.5 — 服务团队
  calling_provider_id?: number | null;
  calling_provider_name?: string | null;
  legal_law_firm_name?: string | null;
  legal_lawyer_name?: string | null;
  legal_order_status?: string | null;
  // v0.6.0 — 案件下「等审批」的法务转化申请;null=无申请。
  // 用于督导端「移交法务 / 审批转法务」按钮条件渲染。
  pending_legal_conversion_request_id?: number | null;
}
