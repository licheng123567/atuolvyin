// v1.6 — 减免审批前端 API hooks（替换 _mock.ts 的 in-memory store）
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";
import type { OfferStatus, OfferType } from "./_mock";

export interface DiscountOfferDTO {
  id: number;
  tenant_id: number;
  case_id: number;
  provider_id: number | null;
  provider_name: string | null;
  applicant_user_id: number | null;
  applicant_role: "agent" | "supervisor";
  applicant_name: string | null;
  case_owner: string | null;
  case_building: string | null;
  project_name: string | null;
  offer_type: OfferType;
  offer_type_label: string;
  original_amount: string;        // Decimal serialized
  proposed_amount: string;
  discount_pct: number;
  installment_months: number | null;
  reason: string;
  status: OfferStatus;
  approver_role_required: "supervisor" | "admin";
  approved_by_user_id: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  rejected_reason: string | null;
  expires_at: string;
  audit_trail: { time: string; actor: string; action: string }[];
  created_at: string;
}

interface ListResp {
  items: DiscountOfferDTO[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListParams {
  myPending?: boolean;
  status?: OfferStatus;
  page?: number;
  pageSize?: number;
}

export function useDiscountOffers(params: ListParams = {}) {
  const query: Record<string, string | number | boolean> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  };
  if (params.myPending) query.my_pending = true;
  if (params.status) query.status = params.status;

  const { query: q } = useCustom<ListResp>({
    url: "discount-offers",
    method: "get",
    config: { query },
  });
  return {
    items: q.data?.data?.items ?? [],
    total: q.data?.data?.total ?? 0,
    isLoading: q.isLoading,
    refetch: q.refetch,
  };
}

export function useDiscountOffer(id: number | undefined) {
  const { query } = useCustom<DiscountOfferDTO>({
    url: id ? `discount-offers/${id}` : "discount-offers/0",
    method: "get",
    queryOptions: { enabled: !!id },
  });
  return {
    offer: query.data?.data,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

interface CreateOfferInput {
  case_id: number;
  offer_type: OfferType;
  original_amount: number;
  proposed_amount: number;
  installment_months: number | null;
  reason: string;
}

/** 创建减免申请。后端按 TenantSettings 阈值自动决定 status。 */
export function useCreateDiscountOffer() {
  const { mutate, mutation } = useCustomMutation<DiscountOfferDTO>();
  const invalidate = useInvalidate();
  return {
    createOffer: (input: CreateOfferInput, opts?: { onSuccess?: (o: DiscountOfferDTO) => void; onError?: (e: unknown) => void }) =>
      mutate(
        {
          url: `cases/${input.case_id}/discount-offers`,
          method: "post",
          values: {
            offer_type: input.offer_type,
            original_amount: input.original_amount,
            proposed_amount: input.proposed_amount,
            installment_months: input.installment_months,
            reason: input.reason,
          },
        },
        {
          onSuccess: (resp) => {
            invalidate({ resource: "discount-offers", invalidates: ["list", "detail"] });
            opts?.onSuccess?.(resp.data as unknown as DiscountOfferDTO);
          },
          onError: (e) => opts?.onError?.(e),
        },
      ),
    isPending: mutation.isPending,
  };
}

export function useApproveOffer() {
  const { mutate, mutation } = useCustomMutation<DiscountOfferDTO>();
  const invalidate = useInvalidate();
  return {
    approve: (id: number, note: string, opts?: { onSuccess?: () => void }) =>
      mutate(
        { url: `discount-offers/${id}/approve`, method: "post", values: { note } },
        {
          onSuccess: () => {
            invalidate({ resource: "discount-offers", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}

export function useRejectOffer() {
  const { mutate, mutation } = useCustomMutation<DiscountOfferDTO>();
  const invalidate = useInvalidate();
  return {
    reject: (id: number, reason: string, opts?: { onSuccess?: () => void }) =>
      mutate(
        { url: `discount-offers/${id}/reject`, method: "post", values: { reason } },
        {
          onSuccess: () => {
            invalidate({ resource: "discount-offers", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}

export function useEscalateOffer() {
  const { mutate, mutation } = useCustomMutation<DiscountOfferDTO>();
  const invalidate = useInvalidate();
  return {
    escalate: (id: number, note: string, opts?: { onSuccess?: () => void }) =>
      mutate(
        { url: `discount-offers/${id}/escalate`, method: "post", values: { note } },
        {
          onSuccess: () => {
            invalidate({ resource: "discount-offers", invalidates: ["list", "detail"] });
            opts?.onSuccess?.();
          },
        },
      ),
    isPending: mutation.isPending,
  };
}
