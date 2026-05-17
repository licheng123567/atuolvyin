import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalCases: () => ({
    items: [
      {
        case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
        building: "1栋", room: "101", project_id: 9, project_name: "阳光花园",
        amount_owed: "3000.00", months_overdue: 3, stage: "跟进中",
      },
    ],
    total: 1, isLoading: false, isError: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalCasesPage } from "../cases/index";

describe("ProviderLegalCasesPage", () => {
  it("renders case row with owner and project", () => {
    render(<MemoryRouter><ProviderLegalCasesPage /></MemoryRouter>);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("阳光花园")).toBeDefined();
    expect(screen.getByText("138****8888")).toBeDefined();
  });
});
