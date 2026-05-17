// §9.1 — 服务商法务前端 API hooks
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";

export interface ProviderLegalCaseListItem {
  case_id: number;
  owner_name: string | null;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  months_overdue: number | null;
  stage: string;
}

export interface ProviderLegalCaseDetail extends ProviderLegalCaseListItem {
  pool_type: string;
  status: string;
  principal_amount: string | null;
  late_fee_amount: string | null;
  arrears_reason: string | null;
  last_contact_at: string | null;
  monthly_contact_count: number;
  priority_score: number;
  call_count: number;
  last_call_at: string | null;
}

export interface ProviderLegalRequestMaterial {
  id: number;
  request_id: number;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_by: number;
  created_at: string;
}

export interface ProviderLegalRequest {
  id: number;
  tenant_id: number;
  case_id: number;
  owner_name: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  reason: string | null;
  status: string;
  reviewer_note: string | null;
  reviewed_at: string | null;
  related_order_id: number | null;
  order_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderLegalRequestDetail extends ProviderLegalRequest {
  materials: ProviderLegalRequestMaterial[];
}

interface ListResp<T> {
  items: T[];
  total: number;
}

export function useProviderLegalCases(params: { page: number; pageSize: number }) {
  const { query } = useCustom<ListResp<ProviderLegalCaseListItem>>({
    url: "provider/legal/cases",
    method: "get",
    config: { query: { page: params.page, page_size: params.pageSize } },
  });
  return {
    items: query.data?.data?.items ?? [],
    total: query.data?.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export function useProviderLegalCase(caseId: number | undefined) {
  const { query } = useCustom<ProviderLegalCaseDetail>({
    url: caseId ? `provider/legal/cases/${caseId}` : "provider/legal/cases/0",
    method: "get",
    queryOptions: { enabled: !!caseId },
  });
  return { detail: query.data?.data, isLoading: query.isLoading, isError: query.isError };
}

export function useProviderLegalRequests(params: { page: number; pageSize: number }) {
  const { query } = useCustom<ListResp<ProviderLegalRequest>>({
    url: "provider/legal/conversion-requests",
    method: "get",
    config: { query: { page: params.page, page_size: params.pageSize } },
  });
  return {
    items: query.data?.data?.items ?? [],
    total: query.data?.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export function useProviderLegalRequest(requestId: number | undefined) {
  const { query } = useCustom<ProviderLegalRequestDetail>({
    url: requestId
      ? `provider/legal/conversion-requests/${requestId}`
      : "provider/legal/conversion-requests/0",
    method: "get",
    queryOptions: { enabled: !!requestId },
  });
  return {
    detail: query.data?.data,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useCreateConversionRequest() {
  const { mutate, mutation } = useCustomMutation<ProviderLegalRequest>();
  const invalidate = useInvalidate();
  return {
    create: (
      caseId: number,
      reason: string,
      opts?: { onSuccess?: (r: ProviderLegalRequest) => void; onError?: (e: unknown) => void },
    ) =>
      mutate(
        {
          url: `provider/legal/cases/${caseId}/conversion-request`,
          method: "post",
          values: { reason },
        },
        {
          onSuccess: (resp) => {
            invalidate({ resource: "provider/legal/conversion-requests", invalidates: ["list"] });
            opts?.onSuccess?.(resp.data as unknown as ProviderLegalRequest);
          },
          onError: (e) => opts?.onError?.(e),
        },
      ),
    isPending: mutation.isPending,
  };
}

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function uploadRequestMaterial(
  requestId: number,
  file: File,
): Promise<ProviderLegalRequestMaterial> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch(
    `${apiBase}/api/v1/provider/legal/conversion-requests/${requestId}/materials`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${localStorage.getItem("autoluyin_token") ?? ""}` },
      body: fd,
    },
  );
  if (!resp.ok) {
    const err = (await resp.json().catch(() => ({}))) as { message?: string };
    throw new Error(err.message ?? `上传失败 (HTTP ${resp.status})`);
  }
  return (await resp.json()) as ProviderLegalRequestMaterial;
}

export async function getMaterialDownloadUrl(
  requestId: number,
  materialId: number,
): Promise<string> {
  const resp = await fetch(
    `${apiBase}/api/v1/provider/legal/conversion-requests/${requestId}/materials/${materialId}`,
    { headers: { Authorization: `Bearer ${localStorage.getItem("autoluyin_token") ?? ""}` } },
  );
  if (!resp.ok) throw new Error(`获取下载链接失败 (HTTP ${resp.status})`);
  const data = (await resp.json()) as { download_url: string };
  return data.download_url;
}
