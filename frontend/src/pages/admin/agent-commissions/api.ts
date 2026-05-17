// §9.2 — 内勤提成前端 API hooks
import { useCustom } from "@refinedev/core";

export interface AgentCommissionItem {
  user_id: number;
  name: string;
  phone_masked: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  paid_case_count: number;
  commission: string;
}

export interface AgentCommissionList {
  year_month: string;
  total_base: string;
  total_commission: string;
  items: AgentCommissionItem[];
}

export interface AgentCommissionLineItem {
  case_id: number;
  owner_name: string;
  paid_amount: string;
  paid_at: string;
  commission_rate: string;
}

export interface AgentCommissionDetail {
  user_id: number;
  name: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  commission: string;
  items: AgentCommissionLineItem[];
}

export function useAgentCommissions(yearMonth: string) {
  const { query } = useCustom<AgentCommissionList>({
    url: "admin/agent-commissions",
    method: "get",
    config: { query: { year_month: yearMonth } },
  });
  return { data: query.data?.data, isLoading: query.isLoading, isError: query.isError };
}

export function useAgentCommissionDetail(userId: number | undefined, yearMonth: string) {
  const { query } = useCustom<AgentCommissionDetail>({
    url: userId ? `admin/agent-commissions/${userId}` : "admin/agent-commissions/0",
    method: "get",
    config: { query: { year_month: yearMonth } },
    queryOptions: { enabled: !!userId },
  });
  return { data: query.data?.data, isLoading: query.isLoading, isError: query.isError };
}
