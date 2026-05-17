import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissions: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { useAgentCommissions } from "../api";
import { AgentCommissionsListPage } from "../index";

const HAPPY_DATA = {
  year_month: "2026-05",
  total_base: "128400.00",
  total_commission: "7020.00",
  items: [
    {
      user_id: 5,
      name: "催收员小王",
      phone_masked: "138****8111",
      year_month: "2026-05",
      commission_rate: 0.057,
      base_amount: "52600.00",
      paid_case_count: 12,
      commission: "3012.00",
    },
  ],
};

describe("AgentCommissionsListPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders summary and agent row", () => {
    vi.mocked(useAgentCommissions).mockReturnValue({
      data: HAPPY_DATA,
      isLoading: false,
      isError: false,
    });
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getByText("催收员小王")).toBeDefined();
    expect(screen.getByText(/7,?020/)).toBeDefined();
  });

  it("shows loading state", () => {
    vi.mocked(useAgentCommissions).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getAllByText("加载中…").length).toBeGreaterThan(0);
  });

  it("shows error state when fetch fails", () => {
    vi.mocked(useAgentCommissions).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getByText("加载失败")).toBeDefined();
  });

  it("shows empty state when items list is empty", () => {
    vi.mocked(useAgentCommissions).mockReturnValue({
      data: { ...HAPPY_DATA, items: [] },
      isLoading: false,
      isError: false,
    });
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getByText("本月无内勤催收员提成数据")).toBeDefined();
  });
});
