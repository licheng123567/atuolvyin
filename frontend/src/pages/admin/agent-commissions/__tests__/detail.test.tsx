import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissionDetail: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { useAgentCommissionDetail } from "../api";
import { AgentCommissionDetailPage } from "../[id]";

const ROUTE = (
  <MemoryRouter initialEntries={["/admin/agent-commissions/5?ym=2026-05"]}>
    <Routes>
      <Route path="/admin/agent-commissions/:id" element={<AgentCommissionDetailPage />} />
    </Routes>
  </MemoryRouter>
);

describe("AgentCommissionDetailPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders agent name and per-case rate (happy path)", () => {
    vi.mocked(useAgentCommissionDetail).mockReturnValue({
      data: {
        user_id: 5,
        name: "催收员小王",
        year_month: "2026-05",
        commission_rate: 0.057,
        base_amount: "52600.00",
        commission: "3012.00",
        items: [
          {
            case_id: 1,
            owner_name: "张三",
            paid_amount: "600.00",
            paid_at: "2026-05-15T00:00:00",
            commission_rate: "0.0800",
          },
        ],
      },
      isLoading: false,
      isError: false,
    });

    render(ROUTE);
    expect(screen.getByText(/催收员小王/)).toBeDefined();
    expect(screen.getByText("8.0%")).toBeDefined();
  });

  it("shows loading state", () => {
    vi.mocked(useAgentCommissionDetail).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(ROUTE);
    expect(screen.getByText("加载中…")).toBeDefined();
  });

  it("shows error state when isError is true", () => {
    vi.mocked(useAgentCommissionDetail).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(ROUTE);
    expect(screen.getByText("未找到提成明细")).toBeDefined();
  });

  it("shows empty state when items list is empty", () => {
    vi.mocked(useAgentCommissionDetail).mockReturnValue({
      data: {
        user_id: 5,
        name: "催收员小王",
        year_month: "2026-05",
        commission_rate: 0.05,
        base_amount: "0.00",
        commission: "0.00",
        items: [],
      },
      isLoading: false,
      isError: false,
    });

    render(ROUTE);
    expect(screen.getByText("本月该催收员无已结案件")).toBeDefined();
  });
});
