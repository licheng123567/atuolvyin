import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalCase: () => ({
    detail: {
      case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
      building: "1栋", room: "101", project_id: 9, project_name: "阳光花园",
      pool_type: "public", stage: "跟进中", status: "active", amount_owed: "3000.00",
      principal_amount: "2800.00", late_fee_amount: "200.00", months_overdue: 3,
      arrears_reason: null, last_contact_at: null, monthly_contact_count: 0,
      priority_score: 1000, call_count: 0, last_call_at: null,
    },
    isLoading: false, isError: false,
  }),
  useCreateConversionRequest: () => ({ create: vi.fn(), isPending: false }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalCaseDetailPage } from "../cases/[id]";

describe("ProviderLegalCaseDetailPage", () => {
  it("renders case info and the create-request button", () => {
    render(
      <MemoryRouter initialEntries={["/provider/legal/cases/1"]}>
        <Routes>
          <Route path="/provider/legal/cases/:id" element={<ProviderLegalCaseDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("发起法务转化请求")).toBeDefined();
  });
});
