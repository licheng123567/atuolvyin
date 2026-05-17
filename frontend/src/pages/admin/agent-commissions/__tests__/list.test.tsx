import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissions: () => ({
    data: {
      year_month: "2026-05", total_base: "128400.00", total_commission: "7020.00",
      items: [
        { user_id: 5, name: "催收员小王", phone_masked: "138****8111", year_month: "2026-05",
          commission_rate: 0.057, base_amount: "52600.00", paid_case_count: 12, commission: "3012.00" },
      ],
    },
    isLoading: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { AgentCommissionsListPage } from "../index";

describe("AgentCommissionsListPage", () => {
  it("renders summary and agent row", () => {
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getByText("催收员小王")).toBeDefined();
    expect(screen.getByText(/7,?020/)).toBeDefined();
  });
});
