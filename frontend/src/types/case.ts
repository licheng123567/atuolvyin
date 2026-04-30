export interface CaseCallItem {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  status: string;
  transcript_preview: string | null;
  result_tag: string | null;
  confidence: number | null;
  agent_name: string | null;
}

export interface TimelineEvent {
  type: string;
  ts: string;
  actor: string | null;
  note: string | null;
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

export interface CaseDetailResponse {
  id: number;
  tenant_id: number;
  project_id: number | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at: string | null;
  monthly_contact_count: number;
  status: string;
  created_at: string;
  updated_at: string;
  calls: CaseCallItem[];
  timeline_events: TimelineEvent[];
}
