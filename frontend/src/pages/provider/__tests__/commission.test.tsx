import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { useCustom } from "@refinedev/core";

vi.mock("@refinedev/core", () => ({
  useCustom: vi.fn(),
  useGo: () => vi.fn(),
}));

import { ProviderMemberCommissionPage } from "../commission/index";

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/provider/team/5/commission"]}>
      <Routes>
        <Route
          path="/provider/team/:user_id/commission"
          element={<ProviderMemberCommissionPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProviderMemberCommissionPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders weighted rate label and per-case project rate column", () => {
    vi.mocked(useCustom).mockReturnValue({
      query: {
        data: {
          data: {
            user_id: 5,
            name: "催收员小李",
            year_month: "2026-05",
            commission_rate: 0.057,
            base_amount: "2600.00",
            commission: "160.00",
            items: [
              {
                case_id: 1,
                owner_name: "张三",
                paid_amount: "600.00",
                paid_at: "2026-05-15T00:00:00",
                commission_rate: "0.1000",
              },
            ],
          },
        },
        isLoading: false,
      },
    } as unknown as ReturnType<typeof useCustom>);

    renderPage();

    expect(screen.getByText(/加权有效率/)).toBeDefined();
    expect(screen.getByText("10.0%")).toBeDefined(); // 逐案项目率
  });

  it("renders empty state when items array is empty", () => {
    vi.mocked(useCustom).mockReturnValue({
      query: {
        data: {
          data: {
            user_id: 5,
            name: "催收员小李",
            year_month: "2026-05",
            commission_rate: 0.057,
            base_amount: "0.00",
            commission: "0.00",
            items: [],
          },
        },
        isLoading: false,
      },
    } as unknown as ReturnType<typeof useCustom>);

    renderPage();

    expect(screen.getByText("该月无已缴费案件")).toBeDefined();
  });

  it("renders loading state when query is in progress", () => {
    vi.mocked(useCustom).mockReturnValue({
      query: {
        data: undefined,
        isLoading: true,
      },
    } as unknown as ReturnType<typeof useCustom>);

    renderPage();

    expect(screen.getByText("加载中…")).toBeDefined();
  });
});
