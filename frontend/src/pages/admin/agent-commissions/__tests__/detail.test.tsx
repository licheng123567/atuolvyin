import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissionDetail: () => ({
    data: {
      user_id: 5, name: "催收员小王", year_month: "2026-05",
      commission_rate: 0.057, base_amount: "52600.00", commission: "3012.00",
      items: [
        { case_id: 1, owner_name: "张三", paid_amount: "600.00",
          paid_at: "2026-05-15T00:00:00", commission_rate: "0.0800" },
      ],
    },
    isLoading: false, isError: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { AgentCommissionDetailPage } from "../[id]";

describe("AgentCommissionDetailPage", () => {
  it("renders agent name and per-case rate", () => {
    render(
      <MemoryRouter initialEntries={["/admin/agent-commissions/5?ym=2026-05"]}>
        <Routes>
          <Route path="/admin/agent-commissions/:id" element={<AgentCommissionDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/催收员小王/)).toBeDefined();
    expect(screen.getByText("8.0%")).toBeDefined();
  });
});
