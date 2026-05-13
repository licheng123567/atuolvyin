// v1.6 — 法务订单前端 API hooks（替换 _mock.ts 的 in-memory store）
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import type { OrderStatus, ServicePackage } from "./_mock";

export interface LegalOrderDTO {
  id: number;
  tenant_id: number;
  tenant_name: string | null;
  case_id: number;
  case_owner: string | null;
  case_building: string | null;
  case_amount: number | null;
  case_months_overdue: number | null;
  project_name: string | null;
  package_id: number;
  package: ServicePackage | null;
  package_label: string;
  status: OrderStatus;
  price_quoted: number;
  platform_fee_amount: number;
  law_firm_id: number | null;
  law_firm_name: string | null;
  lawyer_id: number | null;
  lawyer_name: string | null;
  created_by: string | null;
  created_at: string | null;
  dispatched_at: string | null;
  in_service_at: string | null;
  completed_at: string | null;
  notes: string | null;
  timeline_summary: string | null;
  docs: {
    id: number;
    doc_type: string;
    doc_label: string;
    filename: string;
    uploaded_by: string | null;
    uploaded_at: string | null;
    url: string;
  }[];
}

interface ListResp {
  items: LegalOrderDTO[];
  total: number;
  page: number;
  page_size: number;
}

export interface LawyerLite {
  id: number;
  name: string;
  specialties: string[];
  phone: string | null;
}

type View = "tenant_legal" | "lawfirm" | "lawyer";

function basePathFor(view: View): string {
  if (view === "lawfirm") return "lawfirm";
  if (view === "lawyer") return "lawyer";
  return "legal";
}

export function useLegalOrders(view: View, params: { status?: OrderStatus; page?: number; pageSize?: number } = {}) {
  const query: Record<string, string | number | boolean> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  };
  if (params.status) query.status = params.status;

  const { query: q } = useCustom<ListResp>({
    url: `${basePathFor(view)}/orders`,
    method: "get",
    config: { query },
  });
  return {
    items: q.data?.data?.items ?? [],
    total: q.data?.data?.total ?? 0,
    isLoading: q.isLoading,
    isError: q.isError,
    refetch: q.refetch,
  };
}

export function useLegalOrder(view: View, id: number | undefined) {
  const { query } = useCustom<LegalOrderDTO>({
    url: id ? `${basePathFor(view)}/orders/${id}` : `${basePathFor(view)}/orders/0`,
    method: "get",
    queryOptions: { enabled: !!id },
  });
  return {
    order: query.data?.data,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useLawyersInMyFirm() {
  const { query } = useCustom<LawyerLite[]>({
    url: "lawfirm/lawyers",
    method: "get",
  });
  return {
    lawyers: query.data?.data ?? [],
    isLoading: query.isLoading,
  };
}

export function useAssignLawyer() {
  const { mutate, mutation } = useCustomMutation();
  const invalidate = useInvalidate();
  return {
    assignLawyer: (orderId: number, lawyerId: number, opts?: { onSuccess?: () => void }) =>
      mutate(
        {
          url: `lawfirm/orders/${orderId}/assign-lawyer`,
          method: "post",
          values: { lawyer_id: lawyerId },
        },
        {
          onSuccess: () => {
            invalidate({ resource: "lawfirm/orders", invalidates: ["list", "detail"] });
            invalidate({ resource: "lawyer/orders", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}

export function useUploadDocument() {
  const { mutate, mutation } = useCustomMutation();
  const invalidate = useInvalidate();
  return {
    uploadDoc: (orderId: number, doc: { doc_type: string; filename: string; object_key?: string }, opts?: { onSuccess?: () => void }) =>
      mutate(
        {
          url: `lawyer/orders/${orderId}/upload-document`,
          method: "post",
          values: doc,
        },
        {
          onSuccess: () => {
            invalidate({ resource: "lawyer/orders", invalidates: ["list", "detail"] });
            invalidate({ resource: "legal/orders", invalidates: ["list", "detail"] });
            invalidate({ resource: "lawfirm/orders", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}

export function useCompleteOrder() {
  const { mutate, mutation } = useCustomMutation();
  const invalidate = useInvalidate();
  return {
    completeOrder: (orderId: number, opts?: { onSuccess?: () => void }) =>
      mutate(
        { url: `lawyer/orders/${orderId}/complete`, method: "post", values: {} },
        {
          onSuccess: () => {
            invalidate({ resource: "lawyer/orders", invalidates: ["list", "detail"] });
            invalidate({ resource: "legal/orders", invalidates: ["list", "detail"] });
            invalidate({ resource: "lawfirm/orders", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}
