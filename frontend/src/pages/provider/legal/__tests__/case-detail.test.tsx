import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";

const goMock = vi.fn();

vi.mock("../api", () => ({
  useProviderLegalCase: vi.fn(),
  useCreateConversionRequest: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => goMock }));

import { useProviderLegalCase, useCreateConversionRequest } from "../api";
import { ProviderLegalCaseDetailPage } from "../cases/[id]";

const defaultDetail = {
  case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
  building: "1栋", room: "101", project_id: 9, project_name: "阳光花园",
  pool_type: "public", stage: "跟进中", status: "active", amount_owed: "3000.00",
  principal_amount: "2800.00", late_fee_amount: "200.00", months_overdue: 3,
  arrears_reason: null, last_contact_at: null, monthly_contact_count: 0,
  priority_score: 1000, call_count: 0, last_call_at: null,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/provider/legal/cases/1"]}>
      <Routes>
        <Route path="/provider/legal/cases/:id" element={<ProviderLegalCaseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProviderLegalCaseDetailPage", () => {
  it("renders case info and the create-request button", () => {
    vi.mocked(useProviderLegalCase).mockReturnValue({
      detail: defaultDetail, isLoading: false, isError: false,
    });
    vi.mocked(useCreateConversionRequest).mockReturnValue({ create: vi.fn(), isPending: false });

    renderPage();
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("发起法务转化请求")).toBeDefined();
  });

  it("opens Dialog when clicking '发起法务转化请求'", async () => {
    vi.mocked(useProviderLegalCase).mockReturnValue({
      detail: defaultDetail, isLoading: false, isError: false,
    });
    vi.mocked(useCreateConversionRequest).mockReturnValue({ create: vi.fn(), isPending: false });

    renderPage();
    await userEvent.click(screen.getByText("发起法务转化请求"));
    expect(screen.getByPlaceholderText("请说明转法务的理由（如逾期时长、催收经过等）")).toBeDefined();
  });

  it("shows validation error when submitting with empty reason", async () => {
    vi.mocked(useProviderLegalCase).mockReturnValue({
      detail: defaultDetail, isLoading: false, isError: false,
    });
    vi.mocked(useCreateConversionRequest).mockReturnValue({ create: vi.fn(), isPending: false });

    renderPage();
    await userEvent.click(screen.getByText("发起法务转化请求"));
    await userEvent.click(screen.getByText("提交"));
    expect(screen.getByText("请填写申请理由")).toBeDefined();
  });

  it("navigates to request page on successful submission", async () => {
    goMock.mockReset();
    vi.mocked(useProviderLegalCase).mockReturnValue({
      detail: defaultDetail, isLoading: false, isError: false,
    });
    vi.mocked(useCreateConversionRequest).mockReturnValue({
      create: (_caseId: number, _reason: string, opts?: { onSuccess?: (r: { id: number }) => void; onError?: (e: unknown) => void }) => {
        opts?.onSuccess?.({ id: 7 });
      },
      isPending: false,
    } as unknown as ReturnType<typeof useCreateConversionRequest>);

    renderPage();
    await userEvent.click(screen.getByText("发起法务转化请求"));
    await userEvent.type(screen.getByPlaceholderText("请说明转法务的理由（如逾期时长、催收经过等）"), "逾期超 6 个月，多次催收无果");
    await userEvent.click(screen.getByText("提交"));
    expect(goMock).toHaveBeenCalledWith({ to: "/provider/legal/requests/7" });
  });
});
