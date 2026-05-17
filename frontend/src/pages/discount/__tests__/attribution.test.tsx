import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const baseOffer = {
  id: 1, tenant_id: 1, case_id: 1, applicant_user_id: 2, applicant_role: "agent",
  applicant_name: "王五", case_owner: "张三", case_building: "1栋101", project_name: "阳光花园",
  offer_type: "principal_discount", offer_type_label: "本金减免",
  original_amount: "1000.00", proposed_amount: "800.00", discount_pct: 20,
  installment_months: null, reason: "家庭困难", status: "pending_supervisor",
  approver_role_required: "supervisor", approved_by_user_id: null, approved_by_name: null,
  approved_at: null, rejected_reason: null, expires_at: "2026-05-24T00:00:00",
  audit_trail: [], created_at: "2026-05-17T10:00:00",
};

vi.mock("../api", () => ({
  useDiscountOffers: () => ({
    items: [
      { ...baseOffer, id: 1, provider_id: null, provider_name: null },
      { ...baseOffer, id: 2, provider_id: 5, provider_name: "信达催收" },
      { ...baseOffer, id: 3, provider_id: 7, provider_name: null },
    ],
    total: 3, isLoading: false, refetch: vi.fn(),
  }),
  useApproveOffer: () => ({ approve: vi.fn(), isPending: false }),
  useRejectOffer: () => ({ reject: vi.fn(), isPending: false }),
  useEscalateOffer: () => ({ escalate: vi.fn(), isPending: false }),
}));

vi.mock("../../../hooks/useDiscountPolicy", () => ({
  useDiscountPolicy: () => ({ autoThreshold: 10, supervisorMax: 30, disabled: false, isLoading: false }),
}));

vi.mock("../../../components/ui/HelpPanel", () => ({
  HelpPanel: () => null,
}));

import { ApprovalListPage } from "../ApprovalListPage";

describe("减免归属来源展示", () => {
  it("shows 物业内勤 and 服务商 source", () => {
    render(
      <MemoryRouter>
        <ApprovalListPage
          approverRole="supervisor"
          approverName="测试督导"
          detailBasePath="/supervisor/discount-approvals"
        />
      </MemoryRouter>
    );
    expect(screen.getByText("物业内勤")).toBeDefined();
    expect(screen.getByText(/信达催收/)).toBeDefined();
  });

  it("falls back to #providerId when provider_name is null", () => {
    render(
      <MemoryRouter>
        <ApprovalListPage
          approverRole="supervisor"
          approverName="测试督导"
          detailBasePath="/supervisor/discount-approvals"
        />
      </MemoryRouter>
    );
    expect(screen.getByText(/#7/)).toBeDefined();
  });
});
