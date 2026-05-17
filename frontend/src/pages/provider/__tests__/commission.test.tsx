import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("@refinedev/core", () => ({
  useCustom: () => ({
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
  }),
  useGo: () => vi.fn(),
}));

import { ProviderMemberCommissionPage } from "../commission/index";

describe("ProviderMemberCommissionPage", () => {
  it("renders weighted rate label and per-case project rate column", () => {
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
    expect(screen.getByText(/加权有效率/)).toBeDefined();
    expect(screen.getByText("10.0%")).toBeDefined(); // 逐案项目率
  });
});
